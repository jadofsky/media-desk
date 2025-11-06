# config.py

import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_BASE_URL = "https://openrouter.ai/api/v1"

MEDIA_DESK_CHANNEL = 1435734044439613550

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

# generate every 10 minutes (adjust if needed)
SUMMARY_INTERVAL = 600
