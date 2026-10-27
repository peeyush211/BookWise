"""Canonical genre vocabulary and leakage-free feature helpers.

The catalogue's ``primary_genre`` is the supervised target.  It is deliberately
never included in prediction features because a new book will not have that
label available.  Alias-derived signals are treated as secondary metadata.
"""

from __future__ import annotations

import re
from collections.abc import Mapping


CANONICAL_GENRES = (
    "Fantasy",
    "Romance",
    "Classics",
    "Mystery & Thriller",
    "Nonfiction",
    "Historical Fiction",
    "Science Fiction",
    "General Fiction",
    "Young Adult",
    "Horror",
    "Adventure",
)

_CANONICAL_BY_KEY = {
    genre.casefold().replace("&", "and"): genre for genre in CANONICAL_GENRES
}

# These are intentionally secondary signals.  They do not rewrite the raw
# catalogue label and do not create a new top-level taxonomy at prediction time.
GENRE_ALIASES = {
    "fantasy": "Fantasy",
    "dragon": "Fantasy",
    "dragons": "Fantasy",
    "magic": "Fantasy",
    "magical": "Fantasy",
    "wizard": "Fantasy",
    "wizards": "Fantasy",
    "spell": "Fantasy",
    "spells": "Fantasy",
    "kingdom": "Fantasy",
    "high fantasy": "Fantasy",
    "epic fantasy": "Fantasy",
    "dark fantasy": "Fantasy",
    "urban fantasy": "Fantasy",
    "paranormal fantasy": "Fantasy",
    "sword and sorcery": "Fantasy",
    "magical realism": "Fantasy",
    "romance": "Romance",
    "romantic": "Romance",
    "love story": "Romance",
    "relationship": "Romance",
    "marriage": "Romance",
    "contemporary romance": "Romance",
    "historical romance": "Romance",
    "paranormal romance": "Romance",
    "romantic comedy": "Romance",
    "enemies to lovers": "Romance",
    "classics": "Classics",
    "classic": "Classics",
    "classic literature": "Classics",
    "literary classic": "Classics",
    "mystery": "Mystery & Thriller",
    "mystery and thriller": "Mystery & Thriller",
    "detective": "Mystery & Thriller",
    "murder": "Mystery & Thriller",
    "crime": "Mystery & Thriller",
    "investigation": "Mystery & Thriller",
    "thriller": "Mystery & Thriller",
    "suspense": "Mystery & Thriller",
    "cozy mystery": "Mystery & Thriller",
    "whodunit": "Mystery & Thriller",
    "detective fiction": "Mystery & Thriller",
    "crime fiction": "Mystery & Thriller",
    "psychological thriller": "Mystery & Thriller",
    "police procedural": "Mystery & Thriller",
    "nonfiction": "Nonfiction",
    "non-fiction": "Nonfiction",
    "biography": "Nonfiction",
    "memoir": "Nonfiction",
    "self help": "Nonfiction",
    "self-help": "Nonfiction",
    "personal development": "Nonfiction",
    "true crime": "Nonfiction",
    "essay": "Nonfiction",
    "journalism": "Nonfiction",
    "historical fiction": "Historical Fiction",
    "historical": "Historical Fiction",
    "historical novel": "Historical Fiction",
    "period fiction": "Historical Fiction",
    "historical drama": "Historical Fiction",
    "science fiction": "Science Fiction",
    "sci fi": "Science Fiction",
    "sci-fi": "Science Fiction",
    "scifi": "Science Fiction",
    "space opera": "Science Fiction",
    "space": "Science Fiction",
    "alien": "Science Fiction",
    "aliens": "Science Fiction",
    "futuristic": "Science Fiction",
    "spaceship": "Science Fiction",
    "cyberpunk": "Science Fiction",
    "dystopian": "Science Fiction",
    "post apocalyptic": "Science Fiction",
    "time travel": "Science Fiction",
    "hard science fiction": "Science Fiction",
    "speculative fiction": "Science Fiction",
    "general fiction": "General Fiction",
    "fiction": "General Fiction",
    "contemporary fiction": "General Fiction",
    "literary fiction": "General Fiction",
    "family saga": "General Fiction",
    "womens fiction": "General Fiction",
    "young adult": "Young Adult",
    "ya": "Young Adult",
    "teen": "Young Adult",
    "teen fiction": "Young Adult",
    "coming of age": "Young Adult",
    "new adult": "Young Adult",
    "horror": "Horror",
    "ghost": "Horror",
    "ghosts": "Horror",
    "haunted": "Horror",
    "supernatural": "Horror",
    "terrifying": "Horror",
    "gothic horror": "Horror",
    "psychological horror": "Horror",
    "supernatural horror": "Horror",
    "slasher": "Horror",
    "vampire": "Horror",
    "vampires": "Horror",
    "adventure": "Adventure",
    "journey": "Adventure",
    "expedition": "Adventure",
    "quest": "Adventure",
    "survival": "Adventure",
    "action adventure": "Adventure",
    "exploration": "Adventure",
    "swashbuckler": "Adventure",
    "pirate adventure": "Adventure",
}

_ALIAS_KEYS = sorted(GENRE_ALIASES, key=len, reverse=True)
_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def normalize_text(value: object) -> str:
    """Return a stable, lowercase representation for matching and features."""

    text = str(value or "").casefold().replace("&", " and ")
    return re.sub(r"\s+", " ", _TOKEN_RE.sub(" ", text)).strip()


def normalize_genre_label(value: object) -> str:
    """Map a catalogue label to one of the frozen canonical genres."""

    normalized = normalize_text(value)
    if not normalized:
        return "General Fiction"
    if normalized in _CANONICAL_BY_KEY:
        return _CANONICAL_BY_KEY[normalized]
    return GENRE_ALIASES.get(normalized, "General Fiction")


def split_tags(value: object) -> list[str]:
    """Split comma/semicolon/pipe separated tags while preserving phrases."""

    if value is None:
        return []
    return [part.strip() for part in re.split(r"[,;|\n]+", str(value)) if part.strip()]


def _matches_alias(text: str, alias: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    text_tokens = normalized.split()
    alias_tokens = alias.split()
    if len(alias_tokens) == 1:
        return alias_tokens[0] in text_tokens
    width = len(alias_tokens)
    return any(text_tokens[index:index + width] == alias_tokens for index in range(len(text_tokens) - width + 1))


def infer_genre_signals(*values: object) -> list[str]:
    """Return deduplicated canonical genres signalled by free-form metadata."""

    text = " ".join(normalize_text(value) for value in values if value)
    matches = []
    located_matches = []
    for alias in _ALIAS_KEYS:
        if _matches_alias(text, alias):
            genre = GENRE_ALIASES[alias]
            alias_tokens = alias.split()
            text_tokens = text.split()
            positions = [
                index
                for index in range(len(text_tokens) - len(alias_tokens) + 1)
                if text_tokens[index:index + len(alias_tokens)] == alias_tokens
            ]
            if positions:
                located_matches.append((positions[0], -len(alias_tokens), genre))
    for _, _, genre in sorted(located_matches):
        if genre not in matches:
            matches.append(genre)
    return matches


def unknown_tags(value: object) -> list[str]:
    """Return tag phrases that have no known taxonomy signal.

    This is intentionally conservative: unknown tags are telemetry, not new
    labels.  They are never mapped to a genre automatically.
    """

    unknown = []
    for tag in split_tags(value):
        normalized = normalize_text(tag)
        if not normalized or len(normalized) < 3:
            continue
        if not infer_genre_signals(tag):
            unknown.append(tag.strip())
    return list(dict.fromkeys(unknown))


def build_feature_text(value: Mapping[str, object] | object) -> str:
    """Build model text without using ``primary_genre`` as an input feature."""

    if isinstance(value, Mapping):
        tags = value.get("top_tags") or value.get("tags", "")
        fields = [
            value.get("title", ""),
            value.get("authors", ""),
            tags,
        ]
    else:
        fields = [value]

    raw_text = " ".join(str(field or "") for field in fields).strip()
    signals = infer_genre_signals(*fields)
    signal_text = " ".join(f"genre_signal_{normalize_text(signal).replace(' ', '_')}" for signal in signals)
    return " ".join(part for part in (raw_text, signal_text) if part).strip()


def multilabel_targets(row: Mapping[str, object]) -> list[str]:
    """Create weakly supervised multi-label targets from catalogue metadata.

    The primary label is a real catalogue target.  Additional labels are
    metadata-derived secondary signals until reviewed multi-label annotations
    become available; this limitation is reported by the benchmark output.
    """

    primary = normalize_genre_label(row.get("primary_genre", "General Fiction"))
    labels = [primary]
    for genre in infer_genre_signals(row.get("title"), row.get("authors"), row.get("top_tags")):
        if genre not in labels:
            labels.append(genre)
    return labels
