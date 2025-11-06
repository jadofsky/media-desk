# main.py

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
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "anthropic/claude-3-sonnet-20240229",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a dramatic, story-driven sports journalist. "
                        "Your job is to transform raw league messages into exciting media narratives. "
                        "Focus on rivalries, momentum shifts, breakout stories, upsets, and personality conflicts."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        },
    )

    return response.json()["choices"][0]["message"]["content"].strip()


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
            summary_prompt = "\n".join(messages)
            summary = call_model(summary_prompt)

            personality = random.choice(PERSONALITIES)
            formatted_output = personality(summary)

            output_channel = client.get_channel(MEDIA_DESK_CHANNEL)
            if output_channel:
                await output_channel.send(formatted_output)

        await asyncio.sleep(SUMMARY_INTERVAL)


@client.event
async def on_ready():
    print(f"✅ Media Desk Bot is ONLINE — Logged in as {client.user}")
    client.loop.create_task(media_loop())


client.run(DISCORD_TOKEN)
