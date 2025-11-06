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


def format_headlines(text):
    """
    Ensures headlines are bold and body text normal.
    Rules:
    - Any line starting with a number or "BREAKING" becomes bold.
    - Rest stays normal.
    """
    lines = text.split("\n")
    formatted = []

    for line in lines:
        stripped = line.strip()

        if stripped == "":
            formatted.append("")
            continue

        # Headline rules
        if stripped.upper().startswith("BREAKING") or stripped[0].isdigit():
            formatted.append(f"**{stripped}**")
        else:
            formatted.append(stripped)

    return "\n".join(formatted)


def truncate(text, limit=3500):
    """Avoid Discord max message length (4000)."""
    return text[:limit]


def call_model(prompt):
    try:
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
                        "content": (
                            "You are a dramatic, concise sports media analyst. "
                            "Write like a newsroom feed — headlines bold, body natural, not spammy."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=25
        )
        data = response.json()

        if "choices" not in data:
            return None

        text = data["choices"][0]["message"]["content"].strip()
        return text

    except Exception:
        return None


async def gather_messages(limit_per_channel=30):
    messages = []

    for league, channels in CHANNEL_GROUPS.items():
        for label, ch_id in channels.items():
            if not ch_id:
                continue

            channel = client.get_channel(ch_id)
            if not channel:
                continue

            try:
                async for msg in channel.history(limit=limit_per_channel):
                    if msg.content:
                        messages.append(f"[{league}] {msg.content}")
            except:
                pass

    return messages


async def media_loop():
    await client.wait_until_ready()

    while True:
        messages = await gather_messages()

        if messages:
            combined = "\n".join(messages[:250])

            summary = call_model(combined)
            if summary:
                summary = truncate(summary)
                summary = format_headlines(summary)

                personality = random.choice(PERSONALITIES)
                output = personality(summary)

                channel = client.get_channel(MEDIA_DESK_CHANNEL)
                if channel:
                    await channel.send(output)

        await asyncio.sleep(SUMMARY_INTERVAL)


@client.event
async def on_ready():
    print(f"✅ Media Desk Online — Logged in as {client.user}")
    client.loop.create_task(media_loop())


@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Manual recap trigger (silent)
    if message.content.lower().strip() == "!recap":
        messages = await gather_messages()
        if messages:
            combined = "\n".join(messages[:250])
            summary = call_model(combined)
            if summary:
                summary = truncate(summary)
                summary = format_headlines(summary)

                personality = random.choice(PERSONALITIES)
                output = personality(summary)

                channel = client.get_channel(MEDIA_DESK_CHANNEL)
                if channel:
                    await channel.send(output)


client.run(DISCORD_TOKEN)
