import random

# Ordered list helps rotation feel even
PERSONALITIES = [
    {
        "key": "sas",
        "name": "Stephen A. Smith",
        "style": "Dramatic Outrage",
        "weight": 1.0,
    },
    {
        "key": "shannon",
        "name": "Shannon Sharpe",
        "style": "Unc Energy",
        "weight": 1.0,
    },
    {
        "key": "mcafee",
        "name": "Pat McAfee",
        "style": "High-octane hype & locker-room swagger",
        "weight": 1.0,
    },
    {
        "key": "berman",
        "name": "Chris Berman",
        "style": "Boomer metaphors & big-game cadence",
        "weight": 1.0,
    },
    {
        "key": "olney",
        "name": "Buster Olney",
        "style": "Calm insider narrative",
        "weight": 1.0,
    },
    {
        "key": "herbstreit",
        "name": "Kirk Herbstreit",
        "style": "Culture, preparation, and match-up clarity",
        "weight": 1.0,
    },
    {
        "key": "erin",
        "name": "Erin Andrews",
        "style": "Sideline heartbeat & player emotions",
        "weight": 1.0,
    },
    {
        "key": "holley",
        "name": "Holley Rowe",
        "style": "Warm human angle & perseverance",
        "weight": 1.0,
    },
    {
        "key": "greenberg",
        "name": "Mike Greenberg",
        "style": "Clean anchor analysis — what it means next",
        "weight": 1.0,
    },
]

def pick_personality() -> dict:
    weights = [p["weight"] for p in PERSONALITIES]
    return random.choices(PERSONALITIES, weights=weights, k=1)[0]

def render_name_style(persona: dict) -> str:
    """Format: bold 'Name (Style):' and nothing else."""
    return f"**{persona['name']} ({persona['style']}):**"
