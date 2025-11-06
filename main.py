import discord
import asyncio
import random
import requests

from config import (
    DISCORD_TOKEN,
    OPENROUTER_API_KEY,
    API_BASE_URL,
    MEDIA_DESK_CHANNEL,
    CHANNEL_GROUPS,
    SUMMARY_INTERVAL,
)


# --------------------------------------------------------
# Personality Styles (LIGHT) — Headlines + Social Voice
# --------------------------------------------------------
def headline_style(text):
    lines = text.split("\n")
    formatted = []
    for line in lines:
        line = line.strip()
        if len(line) > 0:
            formatted.append(f"**{line}**")
    return "\n".join(formatted)


def social_commentary_style(text):
    return f"💬 *Media Commentary:* {text}"


PERSONALITIES = [
    headline_style,
    social_commentary_style,
]


# --------------------------------------------------------
# Discord Client Setup
# --------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


# --------------------------------------------------------
# Model Call (MiniMax Free) — No Reasoning Leakage
# --------------------------------------------------------
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
            "include_reasoning": False,   # ✅ Prevents internal chain-of-thought leaking
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a journalistic sports news writer. "
                        "Write short, clean, structured updates. "
                        "Do NOT explain reasoning. Do NOT mention being an AI."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        },
    )

    data = response.json()
    if "choices" not in data:
        return None
    return data["choices"][0]["message"]["content"].strip()


# --------------------------------------------------------
# Message Collection
# --------------------------------------------------------
async def gather_messages(limit=40):
    messages = []
    for league, channels in CHANNEL_GROUPS.items():
        for label, ch_id in channels.items():
            if not ch_id:
                continue

            channel = client.get_channel(ch_id)
            if not channel:
                continue

            if hasattr(channel, "threads") and isinstance(channel, discord.ForumChannel):
                continue  # Skip forum channels

            try:
                async for msg in channel.history(limit=limit):
                    if msg.content:
                        messages.append(f"[{league}] {msg.content}")
            except:
                pass

    return messages


# --------------------------------------------------------
# Core Summary Routine
# --------------------------------------------------------
async def generate_and_send_summary():
    output_channel = client.get_channel(MEDIA_DESK_CHANNEL)
    if not output_channel:
        return

    await output_channel.send("📰 Gathering activity… one moment…")

    messages = await gather_messages()
    if not messages:
        await output_channel.send("⚠️ No recent activity found.")
        return

    prompt = "\n".join(messages[:300])
    result = call_model(prompt)

    if not result:
        await output_channel.send("⚠️ Media Desk could not generate a summary this cycle.")
        return

    personality = random.choice(PERSONALITIES)
    formatted = personality(result)

    if len(formatted) > 3900:
        formatted = formatted[:3900] + "\n…"

    await output_channel.send(formatted)


# --------------------------------------------------------
# Discord Events
# --------------------------------------------------------
@client.event
async def on_ready():
    print(f"✅ Media Desk Bot is ONLINE — Logged in as {client.user}")
    client.loop.create_task(background_loop())


@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.lower() == "!recap":
        await generate_and_send_summary()


# --------------------------------------------------------
# Background Loop
# --------------------------------------------------------
async def background_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        await generate_and_send_summary()
        await asyncio.sleep(SUMMARY_INTERVAL)


# --------------------------------------------------------
# Start Bot
# --------------------------------------------------------
client.run(DISCORD_TOKEN)
