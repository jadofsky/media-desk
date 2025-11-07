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

from personalities import pick_personality, render_name_style
from highlights import generate_headline_post, generate_personality_post


# -------- DISCORD CLIENT -------- #
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


# -------- MODEL CALL -------- #
def call_model(prompt: str) -> str:
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://simsportsgaming.com",
            "X-Title": "SSG Media Desk Bot",
        },
        json={
            "model": "minimax/minimax-m2:free",
            "messages": [
                {"role": "system", "content": "Write with broadcast sports energy."},
                {"role": "user", "content": prompt},
            ],
        },
    ).json()

    if "choices" not in response:
        print("Model error:", response)
        return None

    return response["choices"][0]["message"]["content"].strip()


# -------- MESSAGE GATHERING (Skip Forum Channels) -------- #
async def gather_messages():
    messages = []

    for league, channels in CHANNEL_GROUPS.items():
        for label, ch_id in channels.items():
            if not ch_id:
                continue

            channel = client.get_channel(ch_id)
            if not channel:
                continue

            # Skip Forum channels completely
            if channel.__class__.__name__ == "ForumChannel":
                continue

            try:
                async for msg in channel.history(limit=25):
                    if msg.content:
                        messages.append(msg.content)
            except:
                pass

    return messages


# -------- POST ACTIONS -------- #
async def post_personality_message():
    messages = await gather_messages()
    if not messages:
        return

    persona = pick_personality()
    message_body = generate_personality_post(random.choice(messages))
    formatted = f"{render_name_style(persona)}\n{message_body}"

    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    await channel.send(formatted)


async def post_headline_message():
    messages = await gather_messages()
    if not messages:
        return

    headline = generate_headline_post(messages)
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    await channel.send(headline)


# -------- COMMAND TRIGGERS -------- #
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id != MEDIA_DESK_CHANNEL:
        return

    content = message.content.lower().strip()

    if content == "!persona":
        await post_personality_message()

    elif content == "!highlight":
        await post_headline_message()


# -------- SCHEDULER -------- #
async def scheduler():
    tz = pytz.timezone("US/Eastern")

    while True:
        now = datetime.now(tz)

        # Headlines at 10:00 and 4:00 ET
        if now.hour in (10, 16) and now.minute == 0:
            await post_headline_message()

        # One personality post every hour
        if now.minute == 0:
            await post_personality_message()

        await asyncio.sleep(60)


@client.event
async def on_ready():
    print(f"✅ Bot ONLINE — Logged in as {client.user}")
    client.loop.create_task(scheduler())


client.run(DISCORD_TOKEN)
