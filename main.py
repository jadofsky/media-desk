import os
import re
import asyncio
import random
import textwrap
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import discord
import requests

from config import (
    DISCORD_TOKEN,
    OPENROUTER_API_KEY,
    API_BASE_URL,
    MEDIA_DESK_CHANNEL,
    CHANNEL_GROUPS,   # still used to pull context from your league channels
)

from personalities import PERSONALITIES, pick_persona   # <-- new file below


# ------------- Discord Client & Intents -------------
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

ET = ZoneInfo("America/New_York")

MODEL_ID = "minimax/minimax-m2:free"
POST_MAX_LEN = 1900  # keep < 2000 to be safe in standard channels
CTX_PULL_LIMIT = 60  # per-channel message pull cap
CTX_HOURS_BACK = 48  # lookback window for context (lightweight)
HEADLINE_TOKENS = 500
PERSONA_TOKENS = 320

# 3 personality posts per hour (~every 20 minutes)
PERSONA_INTERVAL_SECONDS = 20 * 60

# Headlines at 10:00 and 16:00 ET
HEADLINE_DROP_TIMES = [(10, 0), (16, 0)]  # (hour, minute) in ET


# ------------- Helpers -------------
def now_et() -> datetime:
    return datetime.now(tz=ET)


def clamp_text(text: str, hard_cap: int = 3000) -> str:
    """Hard-cap model output before Discord split steps."""
    if len(text) <= hard_cap:
        return text
    return text[:hard_cap].rsplit("\n", 1)[0]


async def send_safe(channel: discord.abc.Messageable, text: str):
    """
    Send text safely in chunks under POST_MAX_LEN.
    Prefer paragraph/line boundaries.
    """
    text = text.strip()
    if len(text) <= POST_MAX_LEN:
        await channel.send(text)
        return

    # Split by paragraphs first, then lines
    parts = re.split(r"\n{2,}", text)
    buffer = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # If paragraph itself is too big, split by lines
        if len(p) > POST_MAX_LEN:
            lines = p.split("\n")
            for ln in lines:
                if len(ln) > POST_MAX_LEN:
                    # Final fallback: hard chunk
                    for i in range(0, len(ln), POST_MAX_LEN):
                        await channel.send(ln[i:i+POST_MAX_LEN])
                        await asyncio.sleep(0.3)
                else:
                    if len(buffer) + len(ln) + 1 > POST_MAX_LEN:
                        await channel.send(buffer)
                        buffer = ln
                        await asyncio.sleep(0.3)
                    else:
                        buffer = (buffer + "\n" + ln) if buffer else ln
        else:
            if len(buffer) + len(p) + 2 > POST_MAX_LEN:
                if buffer:
                    await channel.send(buffer)
                    await asyncio.sleep(0.3)
                buffer = p
            else:
                buffer = (buffer + "\n\n" + p) if buffer else p

    if buffer:
        await channel.send(buffer)


def call_model(system_prompt: str, user_prompt: str, max_tokens: int = 500, temperature: float = 0.9) -> str:
    """
    Call OpenRouter with a simple chat.completions schema.
    Returns raw string content or a fallback message on error.
    """
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://simsportsgaming.com",
            "X-Title": "SSG Media Desk Bot",
            "Content-Type": "application/json",
        }
        payload = {
            "model": MODEL_ID,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        resp = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=60)
        data = resp.json()
        # Debug to logs only (never to Discord)
        print("📡 API Response:", {k: data.get(k) for k in ("id", "model", "object")})
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"].strip()
        return "⚠️ (Model returned no content.)"
    except Exception as e:
        print("❌ OpenRouter error:", repr(e))
        return "⚠️ (Temporary content outage.)"


async def pull_context() -> str:
    """
    Pull recent messages from configured channels to create a short context bundle.
    Skips ForumChannel (no .history).
    """
    cutoff = now_et() - timedelta(hours=CTX_HOURS_BACK)
    bundle = []

    for league, channels in CHANNEL_GROUPS.items():
        for label, ch_id in channels.items():
            if not ch_id:
                continue
            channel = client.get_channel(ch_id)
            if not channel:
                continue

            # skip forum channels that don't support .history
            if not hasattr(channel, "history"):
                continue

            try:
                async for msg in channel.history(limit=CTX_PULL_LIMIT, oldest_first=False):
                    if msg.created_at and msg.created_at.replace(tzinfo=timezone.utc) < cutoff.astimezone(timezone.utc):
                        break
                    if msg.content:
                        # keep lines compact; no mentions expansion
                        content = re.sub(r"\s+", " ", msg.content).strip()
                        if content:
                            bundle.append(f"[{league}:{label}] {content}")
            except Exception as e:
                # log silent to console
                print(f"🔒 Skip {league}/{label} ({ch_id}) → {e}")

    # Lightly clamp the context block so prompts stay small/cheap.
    context = "\n".join(bundle[-800:])  # last N lines
    return context


# ------------- Post Generators -------------
def make_headline_prompt(context: str) -> tuple[str, str]:
    system = (
        "You are a breaking-news sports desk that writes Bleacher Report / BR Gridiron style drops. "
        "Always produce a compact post with:\n"
        "• A screaming headline line (caps/emojis OK)\n"
        "• 2–4 ultra-tight lines of context (no more than ~5-8 words each)\n"
        "• Zero hashtags, zero @mentions\n"
        "• Keep total length under 900 characters.\n"
        "Tone: punchy, hype, editorial. No disclaimers, no calls for clarification."
    )
    user = (
        "From the following mixed-league Discord chatter, extract ONE freshest, most compelling item.\n"
        "Write a BR-style drop exactly in this shape:\n\n"
        "🚨 HEADLINE (MAX 12 WORDS)\n"
        "• short line 1\n"
        "• short line 2\n"
        "• short line 3 (optional)\n"
        "• short line 4 (optional)\n\n"
        f"Context:\n{context}"
    )
    return system, user


def make_persona_prompt(persona_name: str, persona_style: str, context: str) -> tuple[str, str]:
    system = (
        "You are posting like a sports media personality on X (formerly Twitter). "
        "Stay fully in-character by tone/mannerisms, but do NOT claim to be the real person. "
        "No requests for clarification. No questions asking the audience what to summarize."
    )
    user = textwrap.dedent(f"""
    Persona: {persona_name} — style guide:
    {persona_style}

    Write ONE short post (X-style), as if reacting to the day’s league chatter below.
    Rules:
    - 1–3 punchy lines, max ~420 characters total
    - Use voice quirks/emojis typical for the persona
    - No @mentions, no hashtags
    - Do NOT ask what to summarize; just deliver a take
    - Keep it readable in Discord
    - No quotes or code fences

    Chatter:
    {context}
    """).strip()
    return system, user


# ------------- Schedulers -------------
async def personality_loop():
    """Every ~20 minutes post a persona take."""
    await client.wait_until_ready()
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    if channel is None:
        print("⚠️ MEDIA_DESK_CHANNEL not found; persona loop idle.")
        return

    while not client.is_closed():
        try:
            context = await pull_context()
            name, style = pick_persona()
            sys, usr = make_persona_prompt(name, style, context)
            out = clamp_text(call_model(sys, usr, max_tokens=PERSONA_TOKENS, temperature=0.95), hard_cap=1200)
            # Prefix with a clean label like an X post
            header = f"{name}:\n"
            await send_safe(channel, header + out)
        except Exception as e:
            print("❌ persona_loop error:", repr(e))
        await asyncio.sleep(PERSONA_INTERVAL_SECONDS)


def seconds_until_next_headline_drop(now: datetime) -> int:
    """
    Compute seconds to the next (10:00 or 16:00 ET) drop from current ET time.
    """
    today = now.date()
    candidates = []
    for hh, mm in HEADLINE_DROP_TIMES:
        dt = datetime(today.year, today.month, today.day, hh, mm, tzinfo=ET)
        if dt > now:
            candidates.append(dt)
    if not candidates:
        # Next day's first drop
        tomorrow = today + timedelta(days=1)
        hh, mm = HEADLINE_DROP_TIMES[0]
        dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hh, mm, tzinfo=ET)
        return int((dt - now).total_seconds())
    nxt = min(candidates)
    return int((nxt - now).total_seconds())


async def headline_loop():
    """Post at 10:00 AM and 4:00 PM ET daily."""
    await client.wait_until_ready()
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    if channel is None:
        print("⚠️ MEDIA_DESK_CHANNEL not found; headline loop idle.")
        return

    while not client.is_closed():
        try:
            wait_s = seconds_until_next_headline_drop(now_et())
            await asyncio.sleep(max(1, wait_s))

            # Time to post a headline
            context = await pull_context()
            sys, usr = make_headline_prompt(context)
            out = clamp_text(call_model(sys, usr, max_tokens=HEADLINE_TOKENS, temperature=0.8), hard_cap=1400)

            # Make sure the very first line looks like a headline (bold + emoji already in text)
            # Only bold the first line, not the whole post.
            lines = out.splitlines()
            if lines:
                lines[0] = f"**{lines[0].strip()}**"
            formatted = "\n".join(lines).strip()

            await send_safe(channel, formatted)

            # Small guard to avoid double-post within the same minute window
            await asyncio.sleep(65)
        except Exception as e:
            print("❌ headline_loop error:", repr(e))
            await asyncio.sleep(60)


# ------------- Discord Events -------------
@client.event
async def on_ready():
    print(f"✅ Media Desk Bot ONLINE — Logged in as {client.user}")
    # Start loops
    asyncio.create_task(personality_loop())
    asyncio.create_task(headline_loop())


# Optional: manual commands (only if you want)
@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Lightweight manual triggers (DM or same channel)
    if message.content.lower().startswith("!headline"):
        context = await pull_context()
        sys, usr = make_headline_prompt(context)
        out = clamp_text(call_model(sys, usr, max_tokens=HEADLINE_TOKENS, temperature=0.8), hard_cap=1400)
        lines = out.splitlines()
        if lines:
            lines[0] = f"**{lines[0].strip()}**"
        await send_safe(message.channel, "\n".join(lines))
        return

    if message.content.lower().startswith("!persona"):
        context = await pull_context()
        name, style = pick_persona()
        sys, usr = make_persona_prompt(name, style, context)
        out = clamp_text(call_model(sys, usr, max_tokens=PERSONA_TOKENS, temperature=0.95), hard_cap=1200)
        await send_safe(message.channel, f"{name}:\n{out}")
        return


# ------------- Run -------------
if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
