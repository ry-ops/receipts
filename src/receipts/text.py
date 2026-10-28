"""Text normalization shared by excerpt and quote matching."""

import re
import unicodedata

_QUOTES = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "−": "-",
    " ": " ", " ": " ", " ": " ",
})
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def normalize(s: str) -> str:
    """Fold the differences that don't change meaning: smart quotes, dashes,
    non-breaking spaces, terminal color codes, runs of whitespace, and case."""
    s = _ANSI.sub("", s)
    s = unicodedata.normalize("NFKC", s).translate(_QUOTES)
    return re.sub(r"\s+", " ", s).strip().casefold()


def contains(haystack: str, needle: str) -> bool:
    n = normalize(needle)
    return bool(n) and n in normalize(haystack)
