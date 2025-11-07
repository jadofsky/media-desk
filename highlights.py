# highlights.py

import random

def generate_headline_post(messages):
    """
    Generate a short, clean headline based on league chatter.
    We are not retelling full stories, just calling out one highlight-worthy item.
    """

    # Extract some useful message fragments to reference
    combined = " ".join(messages).lower()

    candidates = []

    # Detect any signs of hype, big moments, or arguments
    if "game 7" in combined or "series" in combined or "champion" in combined:
        candidates.append("🏆 Championship Drama Continues to Echo Across the League")

    if "trade" in combined:
        candidates.append("🔁 Trade Rumors Heating Up — Front Offices Working the Phones")

    if "injury" in combined or "out" in combined:
        candidates.append("🚑 Key Injury Concerns Begin Shifting Team Strategies")

    if "prospect" in combined or "call up" in combined:
        candidates.append("🌱 Prospect Pipeline Talk Raises Big Future Questions")

    if "budget" in combined or "cap" in combined:
        candidates.append("💰 Offseason Budgets Becoming the Real Battleground")

    # Default fallback if nothing notable is detected
    if not candidates:
        candidates.append("📊 League Storylines Continue to Develop")

    # Return one headline
    return random.choice(candidates)
