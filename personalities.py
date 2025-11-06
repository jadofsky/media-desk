# personalities.py

def samuel_a_loud(summary):
    return f"**SAMUEL A. LOUD REPORTING:**\n{summary.upper()}\nThis is a SEASON-DEFINING moment."

def benny_onyx(summary):
    return f"*Benny Onyx (Insider Notes):*\n{summary}\n(Developing...)"

def adam_shepwell(summary):
    return f"**BREAKING NEWS:** {summary}"

def cassie_crossfade(summary):
    return f"**Cassie Crossfade — Tactical Breakdown**\n{summary}"

def coach_old_head(summary):
    return f"**Coach Henry says:**\n{summary}\nBack in MY day, fundamentals mattered."

def milo_stattenberg(summary):
    return f"**Milo Stattenberg — Analytics Desk**\n{summary}\nInterpret the data how you like."

PERSONALITIES = [
    samuel_a_loud,
    benny_onyx,
    adam_shepwell,
    cassie_crossfade,
    coach_old_head,
    milo_stattenberg
]
