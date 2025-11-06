import os
import discord
import asyncio
import requests
from discord.ext import tasks

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Channel groups (unchanged)
CHANNEL_GROUPS = {
    "OOTP": {
        "discussion": 606606956324454609,
        "recaps": 1079785480633196564,
        "rumors": 803325273725993000,
        "trades": 988152579118755890,
        "news": 1004603096078487642
    },
    "FHM": {
        "discussion": 1171585057677377586,
        "recaps": 1171585293711843401,
        "rumors": 1171585834672205824,
        "trades": 1171585869988249731,
        "news": 1171585732788363284
    },
    "FOF": {
        "discussion": 1041429504054276166,
        "recaps": None,
        "rumors": 1041430538185093130,
        "trades": 1041430578806923294,
        "news": 1041430403438891138
    },
    "CFB": {
        "discussion": 606609107390169108,
        "recaps": 1391431202056962108,
        "rumors": None,
        "trades": None,
        "offseason": 1380206598319767613
    }
}

INTENTS = discord.Intents.default()
INTENTS.messages = True
INTENTS.message_content = True
client = discord.Client(intents=INTENTS)

def call_model(text):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "minimax/minimax-m2:free",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the official league recap writer. "
                    "Format everything clean and structured:\n"
                    "- Use bold headers\n"
                    "- Use short bullet points\n"
                    "- Keep sentences short (no run-ons)\n"
                    "- Maximum 6 short sections total\n"
                    "- Do NOT write long paragraphs\n"
                )
            },
            {"role": "user", "content": text}
        ],
        "max_tokens": 500
    }
    response = requests.post(url, headers=headers, json=data).json()
    return response["choices"][0]["message"]["content"]

def trim_for_discord(content):
    return content[:1990]  # 2000 char limit for messages

@tasks.loop(minutes=60)
async def media_loop():
    await client.wait_until_ready()

    all_messages = []
    print("🔍 Gathering messages now...")

    for league, channels in CHANNEL_GROUPS.items():
        for name, channel_id in channels.items():
            if channel_id is None:
                continue

            try:
                channel = client.get_channel(channel_id)
                if channel:
                    async for msg in channel.history(limit=30):
                        if msg.author != client.user:
                            all_messages.append(f"[{league}/{name}] {msg.author.name}: {msg.content}")
            except:
                pass

    if not all_messages:
        print("⚠️ No messages found.")
        return

    text = "\n".join(all_messages)
    summary = call_model(text)
    summary = trim_for_discord(summary)

    # POST SUMMARY TO MAIN RECAP CHANNEL (OOTP Recaps)
    output_channel = client.get_channel(1079785480633196564)
    if output_channel:
        await output_channel.send(summary)
        print("✅ Recap posted.")
    else:
        print("❌ Output channel not found.")

@client.event
async def on_ready():
    print(f"✅ Media Desk Bot is ONLINE — Logged in as {client.user}")
    media_loop.start()

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.lower() == "!recap":
        await message.channel.send("📰 Gathering activity... one moment...")
        all_messages = []
        for league, channels in CHANNEL_GROUPS.items():
            for name, channel_id in channels.items():
                if channel_id is None:
                    continue
                try:
                    channel = client.get_channel(channel_id)
                    async for msg in channel.history(limit=30):
                        if msg.author != client.user:
                            all_messages.append(f"[{league}/{name}] {msg.author.name}: {msg.content}")
                except:
                    pass

        text = "\n".join(all_messages)
        summary = trim_for_discord(call_model(text))
        await message.channel.send(summary)

client.run(DISCORD_TOKEN)
