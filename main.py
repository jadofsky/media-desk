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
from personalities import PERSONALITIES

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def call_model(prompt):
    print("🛰 Sending prompt to OpenRouter...")

    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://simsportsgaming.com",
            "X-Title": "SSG Media Desk Bot",
            "Content-Type": "application/json",
        },
        json={
            "model": "minimax/minimax-m2:free",  # ✅ FREE MODEL
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a dramatic sports journalist. "
                        "Turn league discussion into narrative storytelling — rivalries, hype, momentum, rising stars."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        },
    )

    data = response.json()
    print("📡 API Response:", data)

    # ✅ If free API fails or MiniMax is unavailable, we return placeholder so bot doesn't break
    if "choices" not in data:
        return "⚠️ Media Desk could not generate a summary this cycle."

    return data["choices"][0]["message"]["content"].strip()


async def gather_messages(limit=60):
    messages = []
    print("🔍 Gathering messages now...")

    for league, channels in CHANNEL_GROUPS.items():
        print(f"📂 Checking League Group: {league}")
        for label, ch_id in channels.items():
            if not ch_id:
                print(f"   → Channel '{label}' skipped (None)")
                continue

            channel = client.get_channel(ch_id)
            if not channel:
                print(f"   → Channel '{label}' not found in client cache")
                continue

            print(f"   → Channel '{label}' with ID: {ch_id}")

            try:
                async for msg in channel.history(limit=limit):
                    if msg.content:
                        messages.append(f"[{league}] {msg.author.display_name}: {msg.content}")
            except Exception as e:
                print(f"     🚫 Permission error → {e}")

    print(f"📨 TOTAL MESSAGES COLLECTED: {len(messages)}")
    return messages


async def media_loop():
    await client.wait_until_ready()
    while True:
        messages = await gather_messages(limit=40)
        if messages:
            summary = call_model("\n".join(messages))
            personality = random.choice(PERSONALITIES)
            formatted = personality(summary)

            output_channel = client.get_channel(MEDIA_DESK_CHANNEL)
            await output_channel.send(formatted)

        await asyncio.sleep(SUMMARY_INTERVAL)


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.lower().startswith("!recap"):
        await message.channel.send("📰 Gathering activity… one moment…")
        messages = await gather_messages(limit=120)
        summary = call_model("\n".join(messages))
        personality = random.choice(PERSONALITIES)
        formatted = personality(summary)
        await message.channel.send(formatted)


@client.event
async def on_ready():
    print(f"✅ Media Desk Bot is ONLINE — Logged in as {client.user}")
    client.loop.create_task(media_loop())


client.run(DISCORD_TOKEN)
