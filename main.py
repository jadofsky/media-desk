import os
import re
import asyncio
import random
import textwrap
from collections import deque, defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
import requests

from config import (
    DISCORD_TOKEN,
    OPENROUTER_API_KEY,
    API_BASE_URL,
    MEDIA_DESK_CHANNEL,
    CHANNEL_GROUPS,  # { "OOTP": {...}, "FHM": {...}, ... }
)

from personalities import PERSONALITIES, pick_personality, render_name_style

# ----------------------------
# Discord client
# ----------------------------
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ----------------------------
# Constants / knobs
# ----------------------------
TZ = ZoneInfo("America/New_York")  # Eastern Time
PERSONALITY_EVERY_MINUTES = 60     # exactly once per hour
HEADLINE_TIMES_ET = [(10, 0), (16, 0)]  # 10:00 & 4:00 PM ET, daily
LOOKBACK_HOURS = 24                # collect last 24h of chatter
PER_CHANNEL_PULL = 60              # messages per channel cap
MESSAGE_CHAR_LIMIT = 1900          # safety margin below Discord's 2000 limit
RECENT_TOPIC_WINDOW = 6            # prevent repetitive topics
REQUEST_TIMEOUT = 45               # seconds

MODEL = "minimax/minimax-m2:free"

# Memory to avoid repeats
recent_personality_topics = deque(maxlen=RECENT_TOPIC_WINDOW)
last_headline_topic = {"text": ""}
last_post_fingerprint = deque(maxlen=8)

# ----------------------------
# Helpers
# ----------------------------

def log(msg: str) -> None:
    print(msg, flush=True)

def now_et() -> datetime:
    return datetime.now(tz=TZ)

def next_run_at(hour: int, minute: int) -> datetime:
    """Next ET run time for a daily schedule at hour:minute."""
    now = now_et()
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate

def fingerprint(text: str) -> str:
    t = re.sub(r"\s+", " ", text.strip().lower())
    return t[:140]

def clamp_discord(text: str) -> str:
    if len(text) <= MESSAGE_CHAR_LIMIT:
        return text
    return text[:MESSAGE_CHAR_LIMIT - 3] + "..."

async def safe_send(channel: discord.abc.Messageable, text: str):
    text = clamp_discord(text)
    if not text.strip():
        return
    fp = fingerprint(text)
    if fp in last_post_fingerprint:
        return  # skip near-duplicate
    await channel.send(text)
    last_post_fingerprint.append(fp)

async def gather_messages():
    """Pull recent messages across configured channels, skipping ForumChannels."""
    cutoff = now_et() - timedelta(hours=LOOKBACK_HOURS)
    collected = defaultdict(list)

    for league, channels in CHANNEL_GROUPS.items():
        for label, ch_id in channels.items():
            if not ch_id:
                continue
            ch = client.get_channel(ch_id)
            if not ch or not hasattr(ch, "history"):
                continue
            try:
                async for m in ch.history(limit=PER_CHANNEL_PULL, oldest_first=False):
                    if not m.created_at:
                        continue
                    # discord.py returns aware UTC datetimes; convert to ET
                    created_et = m.created_at.astimezone(TZ)
                    if created_et < cutoff:
                        break
                    # Ignore bot’s own posts
                    if m.author and getattr(m.author, "bot", False):
                        continue
                    if m.content:
                        collected[league].append(m.content.strip())
            except Exception as e:
                log(f"⚠️ history error: {league}/{label} → {e}")

    # Compact & score by volume
    league_blobs = {}
    for league, msgs in collected.items():
        # Deduplicate near-identical lines and keep order
        seen = set()
        uniq = []
        for t in msgs:
            fp = fingerprint(t)
            if fp not in seen:
                uniq.append(t)
                seen.add(fp)
        league_blobs[league] = "\n".join(uniq)

    return league_blobs  # {league: big_text}


def choose_active_league(league_blobs: dict, exclude_topic_substr: str = "") -> str | None:
    """Pick the league with most fresh content, avoiding repeats by substring."""
    if not league_blobs:
        return None
    # Basic scoring by length; skip leagues that look like the last topic
    ranked = sorted(league_blobs.items(), key=lambda kv: len(kv[1]), reverse=True)
    for league, blob in ranked:
        if exclude_topic_substr and exclude_topic_substr.lower() in blob.lower():
            continue
        if len(blob.strip()) >= 40:
            return league
    # fallback
    return ranked[0][0] if ranked else None


def openrouter_chat(messages, max_tokens=350, temperature=0.8) -> str | None:
    """Call OpenRouter chat endpoint, return assistant content or None."""
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
                "model": MODEL,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": messages,
            },
            timeout=REQUEST_TIMEOUT,
        )
        data = resp.json()
        if "choices" in data and data["choices"]:
            return (data["choices"][0]["message"]["content"] or "").strip()
        return None
    except Exception as e:
        log(f"❌ OpenRouter error: {e}")
        return None


# ----------------------------
# Content Generators
# ----------------------------

async def generate_headline(league: str, blob: str) -> tuple[str, str] | None:
    """
    Return (headline, topic_guard) or None.
    Headlines: AP-style, ≤ 110 chars, no emoji, no markdown.
    """
    system = (
        "You are a wire-service editor. Write a SINGLE crisp AP-style headline "
        "about the most newsworthy update in the provided league chat. "
        "Rules: max 110 characters, no hashtags, no emojis, no markdown, no quotes. "
        "Avoid repeating yesterday's topic; pick a different angle if possible. "
        "Return only the headline text."
    )
    user = f"LEAGUE: {league}\nLATEST CHAT (last 24h):\n{blob[:8000]}"

    text = openrouter_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=60,
        temperature=0.5,
    )
    if not text:
        return None

    headline = text.strip().replace("\n", " ")
    headline = re.sub(r"\s+", " ", headline)
    if len(headline) > 110:
        headline = headline[:107] + "…"

    topic_guard = headline.lower()[:60]
    return headline, topic_guard


async def generate_personality_post(persona: dict, league: str, blob: str) -> tuple[str, str] | None:
    """
    Return (body_text, topic_guard) or None.
    Persona speaks in their voice, 1–3 short lines, no @mentions, minimal emoji.
    """
    persona_name = persona["name"]
    persona_style = persona["style"]

    system = textwrap.dedent(f"""
        You are {persona_name}, voice: {persona_style}.
        Task: Post a short live-feed take about the league's freshest storyline from the chat.
        Constraints:
        - 2 to 4 concise sentences, social-post vibe.
        - No @mentions, no hashtags, no links.
        - Emojis: at most 1, optional. No ALL-CAPS walls.
        - Never ask the reader to clarify; never say you can't parse logs.
        - If the same topic was just covered, pivot to a different angle (coaching move, roster tension,
          fan emotion, next-game stakes, or a quiet storyline).
        Output: plain text only (no name prefix).
    """).strip()

    user = f"LEAGUE: {league}\nLATEST CHAT (last 24h):\n{blob[:8000]}"

    text = openrouter_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=180,
        temperature=0.9,
    )
    if not text:
        return None

    body = text.strip()
    # filter empty or meta replies
    if len(body) < 12 or "I can see you've shared" in body or "clarify" in body.lower():
        return None

    # One emoji max, strip extra
    emojis = re.findall(r"[^\w\s,.'’!?-]", body)
    if len(emojis) > 1:
        # Keep first, remove the rest
        first = emojis[0]
        body = re.sub(r"[^\w\s,.'’!?-]", "", body)
        body = body + " " + first

    # Topic guard = first 60 chars lowercased
    topic_guard = fingerprint(body)[:60]
    return body, topic_guard


# ----------------------------
# Posting wrappers
# ----------------------------

async def post_headline(channel, league_blobs: dict):
    # Pick an active league different from last headline topic, if possible
    league_choice = choose_active_league(league_blobs, exclude_topic_substr=last_headline_topic["text"])
    if not league_choice:
        return

    res = await generate_headline(league_choice, league_blobs[league_choice])
    if not res:
        return
    headline, topic_guard = res

    # Format: simple news ticker look
    out = f"📰 **{headline}**"
    await safe_send(channel, out)
    last_headline_topic["text"] = topic_guard


async def post_personality(channel, league_blobs: dict):
    # Choose personality and an active league whose topic isn't in recent cache
    persona = pick_personality()
    # Try several leagues to avoid repetition
    candidates = list(league_blobs.keys())
    random.shuffle(candidates)

    league_choice = None
    for lg in candidates:
        blob = league_blobs[lg]
        bad = any(t in blob.lower() for t in recent_personality_topics)
        if not bad and len(blob.strip()) >= 40:
            league_choice = lg
            break
    if not league_choice:
        league_choice = choose_active_league(league_blobs)

    if not league_choice:
        return

    res = await generate_personality_post(persona, league_choice, league_blobs[league_choice])
    if not res:
        return
    body, topic_guard = res

    recent_personality_topics.append(topic_guard)

    # Header: bold "Name (Style):" then normal text body
    header = render_name_style(persona)  # e.g., **Stephen A. Smith (Dramatic Outrage):**
    final = f"{header}\n{body}"
    await safe_send(channel, final)


# ----------------------------
# Schedulers
# ----------------------------

async def personality_scheduler():
    await client.wait_until_ready()
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    if not channel:
        log("❌ MEDIA_DESK_CHANNEL not found.")
        return

    log("🟢 Personality loop started.")
    while not client.is_closed():
        league_blobs = await gather_messages()
        if league_blobs:
            try:
                await post_personality(channel, league_blobs)
            except Exception as e:
                log(f"❌ personality post error: {e}")
        # sleep exactly an hour from now (ET-agnostic)
        await asyncio.sleep(PERSONALITY_EVERY_MINUTES * 60)


async def headline_scheduler():
    await client.wait_until_ready()
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    if not channel:
        log("❌ MEDIA_DESK_CHANNEL not found.")
        return

    log("🟢 Headline loop started.")
    while not client.is_closed():
        # compute next headline time (nearest of 10:00 or 16:00 ET)
        now = now_et()
        run_times = [next_run_at(h, m) for (h, m) in HEADLINE_TIMES_ET]
        target = min(run_times, key=lambda dt: dt)
        sleep_sec = (target - now).total_seconds()
        if sleep_sec > 0:
            await asyncio.sleep(sleep_sec)

        league_blobs = await gather_messages()
        if league_blobs:
            try:
                await post_headline(channel, league_blobs)
            except Exception as e:
                log(f"❌ headline post error: {e}")

        # small buffer to avoid double-firing inside same minute
        await asyncio.sleep(5)


# ----------------------------
# Discord events
# ----------------------------

@client.event
async def on_ready():
    log(f"✅ Media Desk Bot ONLINE — Logged in as {client.user}")
    # Start both schedulers
    client.loop.create_task(personality_scheduler())
    client.loop.create_task(headline_scheduler())


# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
