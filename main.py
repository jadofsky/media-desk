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


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def debug_print(msg):
    print(f"[DEBUG] {msg}")


async def gather_messages():
    messages = []
    for league, channels in CHANNEL_GROUPS.items():
        for label, ch_id in channels.items():
            if not ch_id:
                continue
            channel = client.get_channel(ch_id)
            if not channel:
                continue
            if channel.__class__.__name__ == "ForumChannel":
                continue
            try:
                async for msg in channel.history(limit=25):
                    if msg.content:
                        messages.append(msg.content)
            except:
                pass
    return messages


async def post_personality_message():
    debug_print("Posting personality message...")
    messages = await gather_messages()
    if not messages:
        debug_print("No messages gathered.")
        return
    persona = pick_personality()
    message_body = generate_personality_post(random.choice(messages))
    formatted = f"{render_name_style(persona)}\n{message_body}"
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    debug_print(f"Sending to channel: {MEDIA_DESK_CHANNEL}")
    await channel.send(formatted)


async def post_headline_message():
    debug_print("Posting headline...")
    messages = await gather_messages()
    if not messages:
        debug_print("No messages gathered.")
        return
    headline = generate_headline_post(messages)
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    await channel.send(headline)


@client.event
async def on_message(message):
    debug_print(f"Message detected in #{message.channel.id}: {message.content}")

    if message.author == client.user:
        debug_print("Ignoring self message.")
        return

    if message.channel.id != MEDIA_DESK_CHANNEL:
        debug_print(f"Wrong channel. Expected {MEDIA_DESK_CHANNEL}")
        return

    content = message.content.lower().strip()

    if content == "!persona":
        debug_print("!persona detected — running personality")
        await post_personality_message()

    elif content == "!highlight":
        debug_print("!highlight detected — running headline")
        await post_headline_message()


async def scheduler():
    tz = pytz.timezone("US/Eastern")
    while True:
        now = datetime.now(tz)
        if now.hour in (10, 16) and now.minute == 0:
            await post_headline_message()
        if now.minute == 0:
            await post_personality_message()
        await asyncio.sleep(60)


# -------- COMMAND LISTENERS -------- #
@client.event
async def on_message(message):
    # Ignore the bot's own messages
    if message.author == client.user:
        return

    content = message.content.lower().strip()

    # Manual personality post trigger
    if content == "!persona":
        await post_personality_message()
        return

    # Manual headline post trigger
    if content == "!highlight":
        await post_headline_message()
        return

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.lower().strip()

    if content == "!persona":
        await post_personality_message()
        return

    if content == "!highlight":
        await post_headline_message()
        return


client.run(DISCORD_TOKEN)
