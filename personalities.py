# personalities.py

def personality_headline(summary: str):
    # Clean headline formatting
    return f"**🗞️ SSG HEADLINES**\n\n{summary}"

def personality_color(summary: str):
    # Team-beat style voice
    return f"**🎨 Around the League:**\n{summary}"

def personality_clipped(summary: str):
    # Short “X / Twitter” tone: quick takes
    return f"💬 {summary}"

def personality_press_room(summary: str):
    # Neutral newsroom wire writing
    return f"**📡 League Wire Report:**\n{summary}"

# ✅ This is the list main.py imports
PERSONALITIES = [
    personality_headline,
    personality_color,
    personality_clipped,
    personality_press_room
]
