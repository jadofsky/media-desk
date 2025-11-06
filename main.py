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
            "model": "anthropic/claude-3-sonnet",
            "messages": [
                {"role": "system", "content": "You write dramatic sports summaries."},
                {"role": "user", "content": prompt},
            ],
        },
    )

    data = response.json()
    print("📡 Full OpenRouter Response:", data)

    # If OpenRouter returned an error, return generic fallback text
    if "choices" not in data:
        return "⚠️ Media Desk could not generate a summary this cycle."

    return data["choices"][0]["message"]["content"].strip()


async def gather_messages():
    messages = []
    for league, channels in CHANNEL_GROUPS.items():
        for label, ch_id in channels.items():
            if not ch_id:
                continue
            channel = client.get_channel(ch_id)
            if not channel:
                continue
            try:
                async for msg in channel.history(limit=20):
                    if msg.content:
                        messages.append(f"[{league}] {msg.content}")
            except Exception as e:
                print(f"❌ Missing Access → {league}/{label} → {e}")

    print(f"📨 Collected {len(messages)} messages.")
    return messages


async def media_loop():
    await client.wait_until_ready()
    while True:
        messages = await gather_messages()
        if messages:
            text = "\n".join(messages)
            summary = call_model(text)
            personality = random.choice(PERSONALITIES)
            formatted = personality(summary)

            channel = client.get_channel(MEDIA_DESK_CHANNEL)
            if channel:
                await channel.send(formatted)

        await asyncio.sleep(SUMMARY_INTERVAL)


@client.event
async def on_ready():
    print(f"✅ Media Desk Bot is ONLINE — Logged in as {client.user}")
    client.loop.create_task(media_loop())


client.run(DISCORD_TOKEN)
