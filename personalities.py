def headline_writer(summary):
    """
    Formats like ESPN / The Athletic Headlines
    """
    lines = summary.split(". ")
    headline = lines[0].upper()
    return f"**📰 {headline}**\n\n" + summary


def personality_stephen_a(text):
    return f"**Stephen A. Smith (Fired Up):**\nListen... LISTEN! {text} I been TRYING to tell y'all. 🤦🏽‍♂️🔥"


def personality_shannon(text):
    return f"**Shannon Sharpe (Unc Energy):**\nAye lemme tell ya somethin' playa — {text} 🥃🐎"


def personality_doris(text):
    return f"**Doris Burke (Professional Analyst):**\n{text}\n\n— Presented with poise and precision. 🎙️"


def personality_pat_mcafee(text):
    return f"**Pat McAfee Show:**\nHEY BROTHER LISTEN {text.upper()} 💥💥"


def personality_schefty(text):
    return f"**Adam Schefter (BREAKING):**\n🚨 {text}"


def personality_meme(text):
    return f"**League Social Feed:**\n{text} 🤣🤣"


PERSONALITIES = [
    personality_stephen_a,
    personality_shannon,
    personality_doris,
    personality_pat_mcafee,
    personality_schefty,
    personality_meme,
]
