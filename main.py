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
            "HTTP-Referer": "https://simsportsgaming.com",  # recommended for OpenRouter
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
                        "Transform raw league messages into compelling sports media narratives. "
                        "Highlight rivalries, trash talk, momentum swings, heartbreak losses, "
                        "breakout stars, and simmering tensions. Write like ESPN meets WWE drama."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        },
    )

    data = response.json()

    # ✅ Detect & report API errors safely
    if "choices" not in data:
        print("🔥 OpenRouter API ERROR:", data)
        return "⚠️ Media Desk could not generate a summary this cycle. (API Error)"

    # ✅ Get model output
    return data["choices"][0]["message"]["content"].strip()


async def gather_messages():
    messages = []

    for league, channels in CHANNEL_GROUPS.items():
        for label, ch_id in channels.items():
            if not ch_id:
                continue

            channel = client.get_channel(ch_id)
            if channel:
                try:
                    async for msg in channel.history(limit=20):
                        if msg.content:
                            messages.append(f"[{league}] {msg.content}")
                except Exception as e:
                    print(f"❌ Missing Access → {league} / {label} / {ch_id} → {e}")

    print(f"📨 Collected {len(messages)} messages this cycle.")
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

            output_channel = client.get_channel(MEDIA_DESK_CHANNEL)
            if output_channel:
                try:
                    await output_channel.send(formatted_output)
                    print("✅ Posted scheduled media report.")
                except Exception as e:
                    print(f"⚠️ Could not send scheduled message → {e}")

        await asyncio.sleep(SUMMARY_INTERVAL)


@client.event
async def on_ready():
    print(f"✅ Media Desk Bot is ONLINE — Logged in as {client.user}")

    # Run one immediate report
    await asyncio.sleep(5)
    print("📣 Running immediate first media report...")

    messages = await gather_messages()

    if messages:
        combined = "\n".join(messages)
        summary = call_model(combined)
        personality = random.choice(PERSONALITIES)
        formatted_output = personality(summary)

        output_channel = client.get_channel(MEDIA_DESK_CHANNEL)
        if output_channel:
            try:
                await output_channel.send(formatted_output)
                print("✅ Sent immediate report.")
            except Exception as e:
                print(f"⚠️ Could not send immediate message → {e}")

    # Start recurring loop
    client.loop.create_task(media_loop())


client.run(DISCORD_TOKEN)
