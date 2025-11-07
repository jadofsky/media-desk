import random

# -------- HEADLINE POST -------- #
def generate_headline_post(messages: list) -> str:
    """
    Creates a simple headline + short storyline.
    NOT dramatic — clean, short, ESPN bottom-line style.
    """
    if not messages:
        return "**📰 League Update:** No recent discussions."

    sample = messages[-1][:200]  # pick most recent relevant chat

    headlines = [
        "🔥 League Narrative Developing",
        "📰 Storylines Emerging Across the League",
        "⚾ Spotlight on League Momentum",
        "📢 New Buzz Around the Diamond",
    ]

    headline = random.choice(headlines)

    return f"**{headline}**\n{sample}"


# -------- PERSONALITY POST -------- #
def generate_personality_post(message: str) -> str:
    """
    Personalities react to ONE message at a time.
    Kept short, readable, and conversational.
    """
    message = message.strip()

    # Trim long posts
    if len(message) > 180:
        message = message[:160] + "..."

    reactions = [
        f"This one says a LOT.\n> {message}",
        f"Circle this moment.\n> {message}",
        f"People are gonna remember this.\n> {message}",
        f"Here’s the energy right now:\n> {message}",
        f"League conversation is HEATING.\n> {message}",
    ]

    return random.choice(reactions)
