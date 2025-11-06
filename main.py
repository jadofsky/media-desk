import discord
import asyncio
import random
import requests
import os

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
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://simsportsgaming.com",  # Optional but recommended
            "X-Title": "SSG Media Desk Bot",
            "Content-Type": "application/json",
        },
        json={
            "model": "anthropic/claude-3-sonnet",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a dramatic, story-driven sports journalist. "
                        "Transform raw Discord league chatter into engaging narrative stories. "
                        "Focus on rivalries, rising stars, upsets, and emotional stakes."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        },
    )

    data = response.json()

    # ✅ If OpenRouter returned an error, show it in logs
    if "choices" not in data:
        print("🔥 OpenRouter API Error:", data)
        return "⚠️ Media Desk could not generate a summary this cycle."

    return data["choices"][0]["message"]["content"].strip()


async def gather_messages():
    messages = []

    for league, channels in CHANNEL_GROUPS.items():
        for label, ch_id in channels.items():
            if ch_id is None:
                continue

            channel = client.get_channel(ch_id)
            if channel:
                try:
                    async for msg in channel.history(limit=20):
                        if msg.content:
                            messages.append(f"[{league}] {msg.content}")
                except Exception as e:
                    print(f"❌ Missing Access → {league} / {label} / {ch_id} → {e}")

    return messages


async def media_loop():
    await client.wait_until_ready()

    while not client.is_closed():
        messages = await gather_messages()

        if messages:
            combined = "\n".join(messages)
            summary = call_model(combined)

            personality = random.choice(PERSONALITIES)
            formatted_output = personality(summary)

            channel = client.get_channel(MEDIA_DESK_CHANNEL)
            if channel:
                try:
                    await channel.send(formatted_output)
                except Exception as e:
                    print(f"⚠️ Could not send message → {e}")

        await asyncio.sleep(SUMMARY_INTERVAL)


@client.event
async def on_ready():
    print(f"✅ Media Desk Bot is ONLINE — Logged in as {client.user}")

    # Run one report immediately
    await asyncio.sleep(5)
    print("📣 Running immediate media report...")
    messages = await gather_messages()
    if messages:
        summary_prompt = "\n".join(messages)
        summary = call_model(summary_prompt)
        personality = random.choice(PERSONALITIES)
        formatted_output = personality(summary)
        output_channel = client.get_channel(MEDIA_DESK_CHANNEL)
        if output_channel:
            await output_channel.send(formatted_output)
            print("✅ Sent immediate report.")

    client.loop.create_task(media_loop())


client.run(DISCORD_TOKEN)
