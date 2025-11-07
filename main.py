import discord
import asyncio
import random
import requests
import pytz
from datetime import datetime, time

from config import (
    DISCORD_TOKEN,
    OPENROUTER_API_KEY,
    API_BASE_URL,
    MEDIA_DESK_CHANNEL,
    CHANNEL_GROUPS,
)

from personalities import PERSONALITIES   # personalities file stays untouched


### ─────────────────────────────────────────────────────────
### MODEL CALL
### ─────────────────────────────────────────────────────────

def call_model(prompt):
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://simsportsgaming.com",
            "X-Title": "SSG Media Desk Bot",
            "Content-Type": "application/json",
        },
        json={
            "model": "minimax/minimax-m2:free",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a dramatic sports media reporter. Summarize events as compelling stories or headlines."
                },
                {"role": "user", "content": prompt},
            ],
        },
    )

    data = response.json()
    if "choices" not in data:
        return None

    return data["choices"][0]["message"]["content"].strip()


### ─────────────────────────────────────────────────────────
### MESSAGE GATHERING
### ─────────────────────────────────────────────────────────

async def gather_messages():
    messages = []
    for league, channels in CHANNEL_GROUPS.items():
        for _, ch_id in channels.items():
            if not ch_id:
                continue

            channel = client.get_channel(ch_id)
            if not channel:
                continue

            try:
                async for msg in channel.history(limit=20):
                    if msg.content:
                        messages.append(msg.content)
            except:
                pass

    return messages


### ─────────────────────────────────────────────────────────
### CONTENT FORMATTING
### ─────────────────────────────────────────────────────────

def format_headline(text):
    # One bold headline, then clean body
    lines = text.split("\n")
    headline = lines[0][:90].strip(" .!?")  # Keep snappy
    body = " ".join(lines[1:]).strip()

    return f"**{headline}**\n{body}"


def format_personality(name, style_tag, text):
    return f"**{name} ({style_tag}):**\n{text}"


### PERSONALITY MAP (Keep personalities.py unchanged)
PERSONALITY_STYLES = {
    "Pat McAfee": "Amped Take",
    "Shannon Sharpe": "Unc Energy",
    "Buster Olney": "Insider Desk",
    "Adam Schefter": "Breaking Report",
    "Stephen A. Smith": "Loud & Correct",
    "Chris Berman": "RUMBLIN' STUMBLIN'",
    "Kirk Herbstreit": "Analyst Booth",
    "Erin Andrews": "Sideline Report",
    "Holly Rowe": "Feature Spotlight",
    "Mike Greenberg": "Morning Desk",
}


### ─────────────────────────────────────────────────────────
### POSTERS
### ─────────────────────────────────────────────────────────

async def post_headline():
    messages = await gather_messages()
    if not messages:
        return

    text = call_model("\n".join(messages[-60:]))  # last ~60 messages only
    if not text:
        return

    formatted = format_headline(text)
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    await channel.send(formatted[:2000])  # Discord max-safe size


async def post_personality():
    messages = await gather_messages()
    if not messages:
        return

    name, persona_fn = random.choice(list(PERSONALITIES.items()))
    style = PERSONALITY_STYLES.get(name, "Voice")
    raw = call_model("\n".join(messages[-40:]))  # keep smaller sample
    if not raw:
        return

    formatted = format_personality(name, style, raw)
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    await channel.send(formatted[:2000])


### ─────────────────────────────────────────────────────────
### SCHEDULING
### ─────────────────────────────────────────────────────────

async def scheduler():
    est = pytz.timezone("US/Eastern")

    while True:
        now = datetime.now(est).time()

        # 10 AM & 4 PM — headline
        if now.hour in (10, 16) and now.minute == 0:
            await post_headline()

        # Every hour on xx:20 — personality
        if now.minute == 20:
            await post_personality()

        await asyncio.sleep(60)


### ─────────────────────────────────────────────────────────
### MANUAL COMMANDS
### ─────────────────────────────────────────────────────────

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.lower() == "!highlight":
        await post_headline()

    if message.content.lower() == "!persona":
        await post_personality()


### ─────────────────────────────────────────────────────────
### BOT INIT
### ─────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Media Desk Online as {client.user}")
    client.loop.create_task(scheduler())

client.run(DISCORD_TOKEN)
