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
    SUMMARY_INTERVAL
)
from personalities import PERSONALITIES


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


async def send_long_message(channel, content):
    """Ensures all outgoing messages respect Discord's 2000 char limit."""
    chunks = textwrap.wrap(content, width=1900)
    for chunk in chunks:
        await channel.send(chunk)


def call_model(prompt):
    print("🛰 Sending prompt to OpenRouter...")

    # Limit data fed to model
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
                {"role": "system", "content": "Write dramatic but concise sports recaps."},
                {"role": "user", "content": prompt},
            ],
        },
    ).json()

    print("📡 API Response:", response)

    if "choices" not in response:
        return "⚠️ Media Desk could not generate a summary this cycle."

    return response["choices"][0]["message"]["content"].strip()


async def gather_messages():
    messages = []

    print("🔍 Gathering messages now...")
    for league, channels in CHANNEL_GROUPS.items():
        print(f"📂 Checking League Group: {league}")
        for label, ch_id in channels.items():
            if not ch_id:
                continue

            channel = client.get_channel(ch_id)
            if not channel:
                continue

            try:
                async for msg in channel.history(limit=25):
                    if msg.content:
                        messages.append(f"{league}: {msg.author.display_name}: {msg.content}")
            except:
                pass

    print(f"📨 TOTAL MESSAGES COLLECTED: {len(messages)}")
    return messages


async def generate_and_post_summary():
    messages = await gather_messages()

    if not messages:
        return

    combined = "\n".join(messages)
    raw_summary = call_model(combined)

    personality = random.choice(PERSONALITIES)
    final_text = personality(raw_summary)

    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    if channel:
        await send_long_message(channel, final_text)


@client.event
async def on_ready():
    print(f"✅ Media Desk Bot ONLINE — Logged in as {client.user}")
    client.loop.create_task(summary_loop())


async def summary_loop():
    await client.wait_until_ready()
    while True:
        await generate_and_post_summary()
        await asyncio.sleep(SUMMARY_INTERVAL)


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Manual trigger
    if message.content.lower().startswith("!recap"):
        await message.channel.send("📰 Gathering league chatter...")
        await generate_and_post_summary()


client.run(DISCORD_TOKEN)
