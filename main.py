import discord
import asyncio
import random
import requests
import textwrap

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

    # Limit prompt to avoid massive summaries
    prompt = prompt[-4000:]

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
                    "content": (
                        "You are a dramatic sports journalist. Write exciting summaries "
                        "highlighting tension, rivalries, upsets, and narratives."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        },
    )

    data = response.json()
    print("📡 API Response:", data)

    if "choices" not in data:
        return "⚠️ Media Desk could not generate a summary this cycle."

    return data["choices"][0]["message"]["content"].strip()


async def gather_messages():
    messages = []

    print("🔍 Gathering messages now...")
    for league, channels in CHANNEL_GROUPS.items():
        print(f"📂 Checking League Group: {league}")
        for label, ch_id in channels.items():
            if not ch_id:
                print(f"   → Channel '{label}' skipped (None)")
                continue

            print(f"   → Channel '{label}' with ID: {ch_id}")
            channel = client.get_channel(ch_id)
            if not channel:
                print(f"     ⚠️ Channel not found in cache")
                continue

            try:
                async for msg in channel.history(limit=35):
                    if msg.content:
                        messages.append(f"[{league}] {msg.author.display_name}: {msg.content}")

            except Exception as e:
                print(f"     🚫 Permission error → {e}")

    print(f"📨 TOTAL MESSAGES COLLECTED: {len(messages)}")
    return messages


async def send_long_message(channel, content):
    chunks = textwrap.wrap(content, width=1900)
    for chunk in chunks:
        await channel.send(chunk)


async def media_loop():
    await client.wait_until_ready()

    while True:
        messages = await gather_messages()
        if messages:
            combined = "\n".join(messages)
            summary = call_model(combined)
            personality = random.choice(PERSONALITIES)
            formatted = personality(summary)

            channel = client.get_channel(MEDIA_DESK_CHANNEL)
            if channel:
                if len(formatted) > 3900:
                    print("✂️ Splitting long message...")
                    await send_long_message(channel, formatted)
                else:
                    await channel.send(formatted)

        await asyncio.sleep(SUMMARY_INTERVAL)


@client.event
async def on_ready():
    print(f"✅ Media Desk Bot is ONLINE — Logged in as {client.user}")
    client.loop.create_task(media_loop())


client.run(DISCORD_TOKEN)
