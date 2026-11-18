"""Text helpers for the Sinum bridge."""

from __future__ import annotations

MAX_BRIDGE_NAME = 64


def _fix_latin1_run(run: str) -> str:
    try:
        return run.encode("latin1").decode("utf8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return run


def fix_mojibake(value: str) -> str:
    """Repair UTF-8 text that was decoded as Latin-1 one or more times.

    Mixed strings can already contain valid non-Latin-1 characters (e.g.
    ``ż``) next to a still-corrupted prefix. Repair only the Latin-1 runs so
    the already-correct characters do not block the whole-string round-trip.
    """

    text = str(value)
    for _ in range(4):
        parts: list[str] = []
        run: list[str] = []
        for char in text:
            if ord(char) <= 0xFF:
                run.append(char)
                continue
            if run:
                parts.append(_fix_latin1_run("".join(run)))
                run = []
            parts.append(char)
        if run:
            parts.append(_fix_latin1_run("".join(run)))
        fixed = "".join(parts)
        if fixed == text:
            break
        text = fixed
    return text


def bridge_name(friendly_name: str) -> str:
    """Build a Sinum device name from the current HA friendly name."""

    text = fix_mojibake(str(friendly_name)).strip()
    if not text:
        return ""
    if text.startswith("HA · "):
        text = text[5:]
    elif text.startswith("HA "):
        text = text[3:]
    return ("HA · " + text)[:MAX_BRIDGE_NAME].rstrip()
