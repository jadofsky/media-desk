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
            "model": "minimax/minimax-m2",  # ✅ Free & working model
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a dramatic, emotional sports journalist. "
                        "Turn league chatter into compelling stories, rumors, rivalries, and locker room drama. "
                        "Use colorful language and narrative tone."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        },
    )

    data = response.json()
    print("📡 Response Debug:", data)

    if "choices" not in data:
        return "⚠️ Media Desk could not generate a summary this cycle."

    return data["choices"][0]["message"]["content"].strip()


async def gather_past_week_messages():
    messages = []
    print("🔍 Collecting messages…")

    for league, channels in CHANNEL_GROUPS.items():
        for label, ch_id in channels.items():
            if not ch_id:
                continue
            
            channel = client.get_channel(ch_id)
            if not channel:
                print(f"⚠️ Bot cannot see channel: {league}/{label} ({ch_id})")
                continue

            try:
                async for msg in channel.history(limit=200):  # ✅ Pull more = past week+
                    if msg.content:
                        messages.append(f"[{league}] {msg.content}")
            except Exception as e:
                print(f"❌ Missing access → {league}/{label} → {e}")

    print(f"📨 Collected {len(messages)} messages total.")
    return messages


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # ✅ Manual trigger
    if message.content.lower() == "!recap":
        print("🎬 Manual recap triggered.")
        await message.channel.send("📰 Gathering week’s league activity… one moment…")

        messages = await gather_past_week_messages()

        if not messages:
            await message.channel.send("⚠️ I can't see any messages yet. Permissions might still be missing.")
            return

        text = "\n".join(messages)
        summary = call_model(text)

        personality = random.choice(PERSONALITIES)
        final_output = personality(summary)

        target = client.get_channel(MEDIA_DESK_CHANNEL)
        await target.send(final_output)
        await message.channel.send("✅ Media Desk Recap Posted!")


@client.event
async def on_ready():
    print(f"✅ Media Desk Bot ONLINE as {client.user}")


client.run(DISCORD_TOKEN)
