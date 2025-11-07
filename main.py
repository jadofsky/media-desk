import discord
from discord.ext import tasks, commands
import pytz
import datetime
import random
import requests
import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN not found. Set it in Render > Environment.")
if not OPENROUTER_API_KEY:
    raise ValueError("❌ OPENROUTER_API_KEY not found. Set it in Render > Environment.")


from personalities import PERSONALITIES
from highlights import generate_headline_post

# ---- DISCORD INTENTS ----
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# ---- BOT OBJECT ----
client = commands.Bot(command_prefix="!", intents=intents)



### MODEL CALL ###
def call_model(prompt):
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://simsportsgaming.com",
            "X-Title": "SSG Media Desk",
            "Content-Type": "application/json",
        },
        json={
            "model": "minimax/minimax-m2:free",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a concise sports media writer. "
                        "Write clean and structured recaps and commentary. "
                        "Never ramble or repeat. No hashtags. No emojis."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        },
    )

    data = response.json()

    if "choices" not in data:
        return None

    return data["choices"][0]["message"]["content"].strip()


### MESSAGE GATHERING ###
async def gather_messages():
    messages = []

    for league, channels in CHANNEL_GROUPS.items():
        for label, ch_id in channels.items():
            if not ch_id:
                continue

            channel = client.get_channel(ch_id)
            if channel:
                try:
                    async for msg in channel.history(limit=25):
                        if msg.content:
                            messages.append(f"[{league}] {msg.content}")
                except:
                    continue

    return messages


### FORMATTING ###
def format_headline(text):
    lines = text.split("\n")
    title = lines[0].strip().upper()
    body = "\n".join(lines[1:]).strip()
    return f"**{title}**\n{body}"


def format_personality(name, style, text):
    return f"**{name} — {style}**\n{text}"


### SCHEDULERS ###
async def send_headline():
    messages = await gather_messages()
    if not messages:
        return

    prompt = "\n".join(messages)
    result = call_model(prompt)
    if not result:
        return

    formatted = format_headline(result)
    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    await channel.send(formatted)


async def send_personality_post():
    messages = await gather_messages()
    if not messages:
        return

    prompt = "\n".join(messages)
    result = call_model(prompt)
    if not result:
        return

    persona = random.choice(PERSONALITIES)
    name = persona["name"]
    style = persona["style"]
    formatted = format_personality(name, style, result)

    channel = client.get_channel(MEDIA_DESK_CHANNEL)
    await channel.send(formatted)


### MAIN LOOP ###
async def scheduler_loop():
    tz = pytz.timezone("US/Eastern")

    while True:
        now = datetime.now(tz).time()

        # HEADLINES at 10:00 AM and 4:00 PM ET
        if now.hour in [10, 16] and now.minute == 0:
            await send_headline()

        # PERSONALITY once per hour at :20 mark
        if now.minute == 20:
            await send_personality_post()

        await asyncio.sleep(60)


### BOOT EVENT ###
@client.event
async def on_ready():
    print(f"✅ Media Desk Active as {client.user}")
    client.loop.create_task(scheduler_loop())
@client.event
async def on_message(message):
    # ignore bot messages
    if message.author == client.user:
        return

    # let commands work from any channel
    content = message.content.lower()

    if content.startswith("!persona"):
        messages = await gather_messages()
        if not messages:
            return
        prompt = "\n".join(messages)
        result = call_model(prompt)
        if not result:
            return
        persona = random.choice(PERSONALITIES)
        formatted = f"**{persona['name']} — {persona['style']}**\n{result}"
        channel = client.get_channel(MEDIA_DESK_CHANNEL)
        await channel.send(formatted)

    if content.startswith("!highlight"):
        messages = await gather_messages()
        if not messages:
            return
        prompt = "\n".join(messages)
        result = call_model(prompt)
        if not result:
            return
        formatted = format_headline(result)
        channel = client.get_channel(MEDIA_DESK_CHANNEL)
        await channel.send(formatted)


client.run(DISCORD_TOKEN)
