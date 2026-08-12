import re

# Small, deliberately conservative block-list for the in-app order chat.
# This is a basic word filter, not a full trust & safety system.
BANNED_WORDS = {
    "fuck", "shit", "bitch", "asshole", "bastard", "cunt", "dick", "piss",
    "slut", "whore", "faggot", "retard", "nigger", "nigga",
    "bullshit", "shitty", "dumbass", "jackass", "motherfucker",
}

_COLLAPSE_RE = re.compile(r"(.)\1+")


def _collapse(word):
    """fuuuck -> fuck, shiiiit -> shit (collapse repeated letters)."""
    return _COLLAPSE_RE.sub(r"\1", word)


def check_message(text):
    """Return (is_clean, matched_word).

    Checks whole words (so 'Scunthorpe' or 'classic' never match on a
    'cunt'/'ass' substring), with two evasion cases handled: stretched-out
    repeated letters ('fuuuck') and spelling a word out one letter at a
    time with spaces/punctuation ('f.u.c.k', 'f u c k').
    """
    tokens = re.findall(r"[a-zA-Z]+", text.lower())

    for word in tokens:
        if word in BANNED_WORDS or _collapse(word) in BANNED_WORDS:
            return False, word

    # Join runs of single-letter tokens to catch letter-by-letter spelling,
    # without touching ordinary multi-letter words.
    spelled_out = []
    for word in tokens:
        if len(word) == 1:
            spelled_out.append(word)
        else:
            if len(spelled_out) > 1:
                joined = "".join(spelled_out)
                if joined in BANNED_WORDS:
                    return False, joined
            spelled_out = []
    if len(spelled_out) > 1:
        joined = "".join(spelled_out)
        if joined in BANNED_WORDS:
            return False, joined

    return True, None
