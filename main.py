import os
import asyncio
import random
import time
from datetime import datetime, timedelta

import discord
import requests

from config import (
    DISCORD_TOKEN,
    OPENROUTER_API_KEY,
    API_BASE_URL,              # e.g. "https://openrouter.ai/api/v1"
    MEDIA_DESK_CHANNEL,        # int
    CHANNEL_GROUPS,            # dict of {league: {label: channel_id}}
    SUMMARY_INTERVAL,          # seconds (still used as base loop delay)
)

# ---- Personalities (imported) ----------------------------------------------
from personalities import JOURNALISTIC_PERSONALITIES


# ---- Discord client setup ---------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = False
client = discord.Client(intents=intents)


# ---- Tunables for "A, Light" -----------------------------------------------
# 1–2 posts/hour → choose 1 content drop most cycles; occasionally 2
LIGHT_POST_PROBABILITY_SECOND_ITEM = 0.25  # 25% chance to drop a second item in a loop

# Hard caps to avoid 4,000 / 2,000 content errors on Discord
DISCORD_HARD_CAP = 1900  # keep under 2000 safely (unicode/formatting wiggle room)
OPENROUTER_MODEL = "minimax/minimax-m2:free"

# How many messages per channel to fetch and how far back to look
PER_CHANNEL_LIMIT = 50
LOOKBACK_DAYS = 7

# Simple content mix (all in the same channel)
CONTENT_MENU = [
    "HEADLINES",           # 📰 Big bold headlines (desk voice)
    "GAME_RECAP",          # 📊 Concise recap bullets (desk voice)
    "PERSONALITY_TAKE",    # 🎙️ X/Twitter style take (rotating persona)
    "RUMOR_DROP",          # 👁️ Insider/rumor style
]

# Map content type to relative weight (Light cadence still uses one main post)
CONTENT_WEIGHTS = {
    "HEADLINES": 3,
    "GAME_RECAP": 3,
    "PERSONALITY_TAKE": 2,
    "RUMOR_DROP": 2,
}


# ---- Helpers ----------------------------------------------------------------
def _is_textlike(ch: discord.abc.GuildChannel) -> bool:
    """Only pull history from message-based channels: TextChannel, Thread, NewsChannel."""
    return isinstance(ch, (discord.TextChannel, discord.Thread, discord.ForumChannel)) is False and isinstance(
        ch, (discord.TextChannel, discord.Thread, discord.VoiceChannel)
    ) is False  # keep explicit below


def _is_history_capable(ch: discord.abc.GuildChannel) -> bool:
    """ForumChannel objects don't have history(); skip them."""
    return isinstance(ch, (discord.TextChannel, discord.Thread, discord.VoiceChannel)) is False and hasattr(ch, "history")


def chunk_string(s: str, limit: int = DISCORD_HARD_CAP):
    """Yield safe chunks for Discord send() under length limit."""
    while s:
        if len(s) <= limit:
            yield s
            break
        # try to split on double newline or period for cleaner chunks
        cut = s.rfind("\n\n", 0, limit)
        if cut == -1:
            cut = s.rfind(". ", 0, limit)
        if cut == -1:
            cut = limit
        yield s[:cut].strip()
        s = s[cut:].lstrip()


async def safe_send(channel: discord.TextChannel, content: str):
    """Send content split into safe Discord-sized chunks."""
    for part in chunk_string(content, DISCORD_HARD_CAP):
        await channel.send(part)
        await asyncio.sleep(0.5)  # tiny spacing to avoid rate limit bursts


def openrouter_call(prompt: str, system: str, max_tokens: int = 600, temperature: float = 0.8) -> str:
    """Minimal OpenRouter chat call with good logging and graceful failure."""
    try:
        resp = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://simsportsgaming.com",
                "X-Title": "SSG Media Desk Bot",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=60,
        )
        data = resp.json()
        print("📡 API Response:", data)
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"].strip()
        # If error, bubble up something readable for the feed
        if "error" in data:
            return f"⚠️ Media Desk could not generate a summary this cycle. (API {data['error'].get('code','error')})"
        return "⚠️ Media Desk could not generate a summary this cycle."
    except Exception as e:
        print("🧨 OpenRouter Exception:", repr(e))
        return "⚠️ Media Desk could not generate a summary this cycle."


async def collect_messages_window() -> list[str]:
    """Collect recent messages from configured channels in the last LOOKBACK_DAYS, capped per-channel."""
    since = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)
    gathered: list[str] = []

    print("🔍 Gathering messages now...")
    for league, channels in CHANNEL_GROUPS.items():
        print(f"📂 Checking League Group: {league}")
        for label, ch_id in channels.items():
            if not ch_id:
                print(f"   → Channel '{label}' skipped (None)")
                continue

            ch = client.get_channel(ch_id)
            if not ch:
                print(f"   → Channel '{label}' with ID: {ch_id} (not found in cache)")
                continue

            # Skip forum channels (no .history)
            if isinstance(ch, discord.ForumChannel):
                print(f"   → Channel '{label}' with ID: {ch_id} is ForumChannel → skip history")
                continue

            if not hasattr(ch, "history"):
                print(f"   → Channel '{label}' with ID: {ch_id} has no history() → skipping")
                continue

            try:
                print(f"   → Channel '{label}' with ID: {ch_id}")
                pulled = 0
                async for msg in ch.history(limit=PER_CHANNEL_LIMIT, after=since):
                    if msg.content and not msg.author.bot:
                        txt = msg.content.replace("\r", " ").strip()
                        if txt:
                            gathered.append(f"[{league} | #{getattr(ch, 'name', label)}] {txt}")
                            pulled += 1
                print(f"     ✅ Pulled {pulled} messages.")
            except discord.Forbidden as e:
                print(f"     🚫 Permission error → {e}")
            except Exception as e:
                print(f"     ⚠️ Error reading history → {repr(e)}")

    print(f"📨 TOTAL MESSAGES COLLECTED: {len(gathered)}")
    return gathered


def distill_for_prompt(raw_msgs: list[str], max_chars: int = 6000) -> str:
    """
    Distill the raw messages into a compact string to keep prompt size manageable.
    Simple strategy: keep last N within char budget.
    """
    acc = []
    size = 0
    # take the most recent items (end of list) and walk backward
    for m in reversed(raw_msgs):
        if size + len(m) + 1 > max_chars:
            break
        acc.append(m)
        size += len(m) + 1
    # reverse back to chronological order
    acc.reverse()
    return "\n".join(acc)


# ---- Content builders -------------------------------------------------------
def build_headlines_prompt(compact_feed: str) -> tuple[str, str]:
    system = (
        "You are a high-energy ESPN-style sports desk editor. "
        "Return ONLY bold markdown headlines with 1-line subheads. "
        "Format as:\n"
        "📰 **HEADLINE**\n"
        "Subhead sentence.\n"
        "—\n"
        "📰 **HEADLINE**\n"
        "Subhead sentence.\n"
        "Keep it punchy. No intros, no closers, no emojis beyond the newspaper icon."
    )
    user = (
        "From the following league feed fragments, produce 3–5 bold headlines with one-line subheads. "
        "Prioritize big results, upsets, trades, injuries, and GM drama.\n\n"
        f"FEED:\n{compact_feed}"
    )
    return system, user


def build_game_recap_prompt(compact_feed: str) -> tuple[str, str]:
    system = (
        "You are a professional recap writer. "
        "Write a concise *news desk* recap in 6–10 short bullets. "
        "Format bullets with '•' and use **bold** for team names/players. "
        "No intro/closing paragraphs—just the bullets."
    )
    user = (
        "Summarize the most recent key results and storylines in plain bullets:\n\n"
        f"{compact_feed}"
    )
    return system, user


def build_rumor_prompt(compact_feed: str) -> tuple[str, str]:
    system = (
        "You are an 'Insider' rumor reporter. "
        "Output a short 'Rumor Mill' post: a bold title, then 4–7 tight bullet items. "
        "Each bullet should read like a sourced whisper (use 'Per sources', 'Hearing', 'Early chatter'). "
        "Avoid absolutes; keep it plausible. No hashtags."
    )
    user = f"From this feed, extract active trade/free agency buzz:\n\n{compact_feed}"
    return system, user


def build_personality_prompt(compact_feed: str) -> tuple[str, str]:
    system = (
        "You write a single X/Twitter-style post (max ~300 chars) reacting to the latest league events. "
        "Spicy but not toxic. No hashtags. No @ mentions. No links. One short paragraph only."
    )
    user = f"Draft one take based on the most recent highlights:\n\n{compact_feed}"
    return system, user


async def produce_content(feed: list[str]) -> list[str]:
    """Generate 1–2 posts per cycle with mixed content style, all formatted for Discord."""
    posts: list[str] = []
    if not feed:
        return posts

    compact = distill_for_prompt(feed, max_chars=6000)

    # Choose 1 main content type
    choices = []
    for k, w in CONTENT_WEIGHTS.items():
        choices += [k] * w
    primary = random.choice(choices)

    plan = [primary]

    # Sometimes add a second drop (light cadence)
    if random.random() < LIGHT_POST_PROBABILITY_SECOND_ITEM:
        second = random.choice(choices)
        if second != primary:
            plan.append(second)

    for kind in plan:
        if kind == "HEADLINES":
            system, user = build_headlines_prompt(compact)
            raw = openrouter_call(user, system, max_tokens=500, temperature=0.8)
            # Ensure clear separators between items
            text = raw.strip()
            if not text.lower().startswith("📰"):
                text = "📰 **LEAGUE HEADLINES**\n" + text
            posts.append(text)

        elif kind == "GAME_RECAP":
            system, user = build_game_recap_prompt(compact)
            raw = openrouter_call(user, system, max_tokens=450, temperature=0.7)
            header = "📊 **Quick Recap**"
            posts.append(f"{header}\n{raw}")

        elif kind == "RUMOR_DROP":
            system, user = build_rumor_prompt(compact)
            raw = openrouter_call(user, system, max_tokens=450, temperature=0.9)
            if not raw.lower().startswith("**rumor"):
                raw = f"👁️ **Rumor Mill**\n{raw}"
            posts.append(raw)

        elif kind == "PERSONALITY_TAKE":
            # Pick a personality and wrap their X-style line
            persona = random.choice(JOURNALISTIC_PERSONALITIES)
            system, user = build_personality_prompt(compact)
            take = openrouter_call(user, system, max_tokens=160, temperature=0.95)
            posts.append(persona(take))

    # Hard-trim any post that still risks discord limits
    trimmed = []
    for p in posts:
        if len(p) > DISCORD_HARD_CAP:
            p = p[: DISCORD_HARD_CAP - 3].rstrip() + "…"
        trimmed.append(p)

    return trimmed


# ---- Main loop --------------------------------------------------------------
async def media_loop():
    await client.wait_until_ready()
    print("🟢 Media loop started.")
    output_channel = client.get_channel(MEDIA_DESK_CHANNEL)
    if not isinstance(output_channel, discord.TextChannel):
        print("🛑 MEDIA_DESK_CHANNEL not found or not a text channel.")
        return

    while not client.is_closed():
        try:
            feed = await collect_messages_window()
            drops = await produce_content(feed)
            for post in drops:
                await safe_send(output_channel, post)
                await asyncio.sleep(1.0)

        except Exception as e:
            print("🧨 Loop Exception:", repr(e))

        # Light cadence—use whatever you already set in SUMMARY_INTERVAL
        await asyncio.sleep(SUMMARY_INTERVAL)


@client.event
async def on_ready():
    print(f"✅ Media Desk Bot is ONLINE — Logged in as {client.user}")
    client.loop.create_task(media_loop())


# Optional manual trigger: !recap (kept short & safe)
@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.content.strip().lower().startswith("!recap"):
        if message.channel.id != MEDIA_DESK_CHANNEL:
            await message.channel.send("Use this in the Media Desk channel.")
            return
        await message.channel.trigger_typing()
        feed = await collect_messages_window()
        drops = await produce_content(feed)
        if not drops:
            await message.channel.send("No recent activity to recap.")
            return
        for post in drops:
            await safe_send(message.channel, post)


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
