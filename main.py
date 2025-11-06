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


# ---------------------------------------------------------
# MODEL CALL
# ---------------------------------------------------------
def call_model(prompt):
    print("🛰 Sending summary request to OpenRouter...", flush=True)

    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://simsportsgaming.com",
            "X-Title": "SSG Media Desk Bot",
            "Content-Type": "application/json",
        },
        json={
            "model": "minimax/minimax-m2",  # ✅ free model
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a dramatic, story-driven sports journalist. "
                        "Turn raw league chat into compelling narratives. Focus on rivalries, emotion, hype, and story arcs."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        },
        timeout=25,
    )

    data = response.json()
    print("📡 MODEL RESPONSE:", data, flush=True)

    # If API error, return fallback
    if "choices" not in data:
        print("❌ Model returned no choices (API issue)", flush=True)
        return "⚠️ Media Desk could not generate a summary this cycle."

    return data["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------
# MESSAGE GATHERING & DEBUG
# ---------------------------------------------------------
async def gather_messages():
    messages = []
    print("🔍 Gathering messages now...", flush=True)

    for league, channels in CHANNEL_GROUPS.items():
        print(f"📂 Checking League Group: {league}", flush=True)

        for label, ch_id in channels.items():
            print(f"   → Channel '{label}' with ID: {ch_id}", flush=True)

            if not ch_id:
                print("     ⚠️ No ID provided, skipping", flush=True)
                continue

            channel = client.get_channel(ch_id)
            if not channel:
                print("     ❌ Could not resolve channel. (Bad ID or bot not in server)", flush=True)
                continue

            print(f"     ✅ Accessing channel: {channel.name}", flush=True)

            try:
                async for msg in channel.history(limit=20):
                    if msg.author.bot:
                        continue
                    if msg.content:
                        messages.append(f"[{league}:{label}] {msg.author.display_name}: {msg.content}")
                print("     ✅ Message pull complete.", flush=True)
            except Exception as e:
                print(f"     🚫 Permission error → {e}", flush=True)

    print(f"📨 TOTAL MESSAGES COLLECTED THIS CYCLE: {len(messages)}", flush=True)
    return messages


# ---------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------
async def media_loop():
    await client.wait_until_ready()
    while True:
        messages = await gather_messages()

        if messages:
            combined_text = "\n".join(messages)
            summary = call_model(combined_text)
            personality = random.choice(PERSONALITIES)
            final_output = personality(summary)

            channel = client.get_channel(MEDIA_DESK_CHANNEL)
            if channel:
                try:
                    await channel.send(final_output)
                    print("✅ Sent Media Desk update.", flush=True)
                except Exception as e:
                    print(f"⚠️ Failed to send message → {e}", flush=True)
        else:
            print("🟡 No messages found. Skipping model call.", flush=True)

        await asyncio.sleep(SUMMARY_INTERVAL)


# ---------------------------------------------------------
# STARTUP EVENTS
# ---------------------------------------------------------
@client.event
async def on_ready():
    print(f"✅ Media Desk Bot ONLINE — Logged in as {client.user}", flush=True)

    # Run instant test summary
    await asyncio.sleep(5)
    print("🚀 Running Initial Startup Summary...", flush=True)
    test_messages = await gather_messages()

    if test_messages:
        combined_text = "\n".join(test_messages)
        summary = call_model(combined_text)
        personality = random.choice(PERSONALITIES)
        final_output = personality(summary)

        channel = client.get_channel(MEDIA_DESK_CHANNEL)
        if channel:
            await channel.send(final_output)
            print("✅ Initial summary posted.", flush=True)
    else:
        print("🟡 No messages found for initial run.", flush=True)

    client.loop.create_task(media_loop())


client.run(DISCORD_TOKEN)
