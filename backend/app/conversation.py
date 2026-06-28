"""Lightweight, deterministic small-talk handling so agents respond politely to
greetings and pleasantries even when no language model is configured. Analytics
and delegation are checked first by the caller, so a real request that merely
starts with "hi" is never hijacked."""

import re

_GREET_WORDS = {
    "hi", "hii", "hello", "hellow", "hey", "heya", "hiya", "yo", "howdy",
    "greetings", "sup", "namaste",
}
_GREET_PHRASES = (
    "good morning", "good afternoon", "good evening", "good day",
    "what's up", "whats up", "g'day",
)
_THANKS = ("thank you", "thanks", "thank u", "thx", "cheers", "much appreciated", "appreciate")
_FAREWELL_WORDS = {"bye", "goodbye", "farewell", "ttyl"}
_FAREWELL_PHRASES = ("good bye", "see you", "see ya", "take care", "catch you later")
_HOW = ("how are you", "how're you", "how r u", "how are u", "how's it going",
        "hows it going", "how do you do")


def detect_social(message: str) -> str | None:
    """Classify a message as 'greeting' | 'thanks' | 'farewell' | 'howareyou',
    or None if it is not (purely) small talk."""
    t = (message or "").strip().lower()
    words = re.findall(r"[a-z']+", t)
    if not words:
        return None
    if len(words) > 6:  # long messages are real requests, not small talk
        return None
    first = words[0]
    if any(p in t for p in _HOW):
        return "howareyou"
    if any(p in t for p in _THANKS):
        return "thanks"
    if first in _FAREWELL_WORDS or any(p in t for p in _FAREWELL_PHRASES):
        return "farewell"
    if first in _GREET_WORDS or any(p in t for p in _GREET_PHRASES):
        return "greeting"
    return None


_GENERIC = {
    "greeting": (
        "Hello! I'm your ShowSphere assistant for this show. I can answer questions "
        "about the project's data, build charts, and crunch the numbers — what "
        "would you like to explore?"
    ),
    "thanks": (
        "You're very welcome — glad to help! Is there anything else about the "
        "show you'd like to look into?"
    ),
    "farewell": (
        "Goodbye for now, and thanks for stopping by! I'm here whenever you need "
        "a hand with the show."
    ),
    "howareyou": (
        "I'm doing great, thank you for asking! Ready to dig into this show's "
        "data whenever you are — what can I help with?"
    ),
}

_BOOTH = {
    "greeting": (
        "Hello! I'm your booth layout planner. Tell me about your stand — the "
        "size (e.g. 6×4 m), the type (inline, corner, peninsula, or island), and "
        "the zones you'd like — and I'll design the layout for you."
    ),
    "thanks": (
        "You're welcome — happy to help! Want me to tweak the layout or add a zone?"
    ),
    "farewell": (
        "Goodbye, and good luck with your stand! Come back any time to refine the "
        "layout."
    ),
    "howareyou": (
        "Doing well, thanks! Ready to plan your booth — just tell me the size, "
        "type, and the zones you'd like."
    ),
}


def social_reply(message: str, *, booth: bool = False) -> str | None:
    kind = detect_social(message)
    if kind is None:
        return None
    return (_BOOTH if booth else _GENERIC)[kind]
