import discord
import asyncio
import random
import requests
from datetime import datetime
import pytz

from config import (
    DISCORD_TOKEN,
    OPENROUTER_API_KEY,
    API_BASE_URL,
    MEDIA_DESK_CHANNEL,
    CHANNEL_GROUPS,
)
from personalities import PERSONALITIES, headline_writer


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Track daily headline posts so we don't double-fire
did_morning_headline = False
did_evening_headline = False


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
            "messages": [
                {
                    "role": "system",
                    "content": "You write clean, concise sports summaries. One paragraph maximum."
                },
                {"role": "user", "content": prompt},
            ],
        },
    )

    data = response.json()
    if "choices" not in data:
        print("API Error:", data)
        return None

    return data["choices"][0]["message"]["content"].strip()


async def gather_messages():
    messages = []
    for league, channels in CHANNEL_GROUPS.items():
        for label, channel_id in channels.items():
            if not channel_id:
                continue
            channel = client.get_channel(channel_id)
            if not channel:
                continue
            try:
                async for msg in channel.history(limit=25):
                    if msg.content:
                        messages.append(msg.content)
            except:
                pass
    return messages


async def send_headline_post():
    messages = await gather_messages()
    if not messages:
        return

    combined = "\n".join(messages[:250])
    summary = call_model(combined)
    if not summary:
        return

    post = headline_writer(summary)
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    if channel:
        await channel.send(post)


async def send_personality_post():
    personality = random.choice(PERSONALITIES)
    messages = await gather_messages()

    # Light or no input ok
    text = "\n".join(messages[:200]) if messages else "General league atmosphere."
    response = call_model(text)
    if not response:
        return

    post = personality(response)
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    if channel:
        await channel.send(post)


async def scheduler():
    global did_morning_headline, did_evening_headline

    while True:
        now = datetime.now(pytz.timezone("US/Eastern"))
        hour = now.hour
        minute = now.minute

        # ✅ Reset daily headline flags at midnight
        if hour == 0 and minute == 0:
            did_morning_headline = False
            did_evening_headline = False

        # ✅ 10 AM ET Headline
        if hour == 10 and not did_morning_headline:
            await send_headline_post()
            did_morning_headline = True

        # ✅ 4 PM ET Headline
        if hour == 16 and not did_evening_headline:
            await send_headline_post()
            did_evening_headline = True

        # ✅ Personality chatter every ~20 min
        if minute % 20 == 0:
            await send_personality_post()

        await asyncio.sleep(60)


@client.event
async def on_ready():
    print(f"✅ Media Desk Bot ONLINE — Logged in as {client.user}")
    client.loop.create_task(scheduler())


client.run(DISCORD_TOKEN)
