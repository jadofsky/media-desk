# Journalistic / broadcast-style personas for X/Twitter-style posts.
# Each returns a short block formatted like a social post (name + one take).

def _x_post(display: str, handle: str, text: str) -> str:
    # Keep it tight; Discord-safe
    text = text.strip().replace("\n", " ")
    if len(text) > 300:
        text = text[:297].rstrip() + "…"
    header = f"**{display}** — {handle}"
    return f"{header}\n{text}"

def SAMUEL_A_LOUD(take: str) -> str:
    # Arena voice, hype, big energy
    return _x_post("Samuel A. Loud", "@ArenaVoice",
                   take)

def CASSIE_CROSSFADE(take: str) -> str:
    # Tactical breakdown, sharp, TV analyst vibe
    return _x_post("Cassie Crossfade — Tactical Breakdown", "@CassieChalk",
                   take)

def MILO_STATTENBERG(take: str) -> str:
    # Analytics forward, nerdy bite
    return _x_post("Milo Stattenberg — Analytics Desk", "@MiloModels",
                   take)

def UNCLE_DALE(take: str) -> str:
    # Blue-collar fan energy, spicy but not toxic
    return _x_post("Uncle Dale", "@DaleAtTheBar",
                   take)

def THE_INSIDER(take: str) -> str:
    # Insider whisper vibe (short, coy)
    return _x_post("The Insider", "@SSGWhispers",
                   take)

JOURNALISTIC_PERSONALITIES = [
    SAMUEL_A_LOUD,
    CASSIE_CROSSFADE,
    MILO_STATTENBERG,
    UNCLE_DALE,
    THE_INSIDER,
]
