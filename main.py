#!/usr/bin/env python3

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_IGNORE_FILE = BASE_DIR / "assets" / "ignore.txt"
DEFAULT_ARTIST_FILE = BASE_DIR / "assets" / "artist.txt"

_TRANSLATE = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\uff0d": "-",
        "\u2043": "-",
        "\u2015": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u2032": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2033": '"',
        "\u3010": "[",
        "\u3011": "]",
        "\u3014": "[",
        "\u3015": "]",
        "\u3016": "[",
        "\u3017": "]",
        "\u3018": "[",
        "\u3019": "]",
        "\u301a": "[",
        "\u301b": "]",
        "\uff08": "(",
        "\uff09": ")",
        "\u300c": '"',
        "\u300d": '"',
        "\u300e": '"',
        "\u300f": '"',
        "\u00b7": "|",
        "\u2022": "|",
        "\u2023": "|",
        "\u25aa": "|",
        "\u25cf": "|",
        "\u25b8": "|",
        "\u25b6": "|",
        "\u25c6": "|",
        "\u2027": "|",
        "\u2026": "...",
        "\u2044": "/",
        "\u2215": "/",
        "\u00ad": "",
    }
)

_ZERO_WIDTH_RE = re.compile("[\u180e\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_SPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"\S+")

_EDGE_CHARS = "\t\n\r _-:;,.?!'\"`()[]{}<>|*#~/\\"
_EDGE_PUNCT = " \t\"'`.,:;!?()[]{}<>|_~*#…-+/\\"
_EXTRAS_EDGE = " \t\n\r|:;,-~*+/\\"

_SPLIT_RE = re.compile(r"[ \t]*(?:[-–—][ \t]+|[|｜ǀ│┃•·‧・»›▸►●▪▶][ \t]*)")

_BRACKETS = {"(": ")", "[": "]", "{": "}"}
_CLOSERS = {v: k for k, v in _BRACKETS.items()}

_TECH_RES = (
    re.compile(r"\d{3,4}p"),
    re.compile(r"\d{2,3}fps"),
    re.compile(r"\d{2,4}kbps"),
    re.compile(r"\d{3,4}x\d{3,4}"),
    re.compile(r"\d{1,3}:\d{2}(?::\d{2})?"),
)
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
_NUMBER_RE = re.compile(r"\d{1,3}")


PROTECTED_WORDS = frozenset(
    """old new latest original release version full live cover song songs
    video videos audio music clean dirty""".split()
)


VERSION_WORDS = frozenset(
    """acoustic unplugged orchestral piano instrumental karaoke demo session
    live remix edit reprise nightcore slowed sped speeded reverb bootleg mashup
    flip extended deluxe remaster remastered bonus mono stereo version single
    album original clean dirty radio club concert instrumental""".split()
)

_CREDIT_LABEL_SRC = (
    r"feat\.?|ft\.?|featuring|prod\.?|produced\s+by|mix(?:ed)?\s+by|"
    r"master(?:ed)?\s+by|cover(?:ed)?\s+by|remix(?:ed)?\s+by|edit(?:ed)?\s+by|"
    r"sang\s+by|singer|vocalist|composed\s+by|composer|lyrics?\s+by|written\s+by"
)

FREE_CREDIT_RE = re.compile(rf"^({_CREDIT_LABEL_SRC})(?!\w)[\s:\-]*", re.I)
GROUP_CREDIT_RE = re.compile(
    rf"^({_CREDIT_LABEL_SRC}"
    r"|from|in|on|album|movie|film|soundtrack|director|label|record\s+label"
    r"|song|track|season|episode|part|starring|with)(?!\w)\s*[:\-]?\s*(.+)$",
    re.I | re.S,
)
_FEATURE_LABELS = frozenset({"feat", "ft", "featuring"})
_COLLAB_TOKENS = frozenset(
    {"&", "x", "vs", ",", "and", "/", "+", "feat", "ft", "featuring", "with"}
)


def is_collab_token(token: Token) -> bool:

    raw = token.raw
    if fold(raw.strip(_EDGE_PUNCT)) in _COLLAB_TOKENS:
        return True
    return bool(raw) and raw[-1] in ",&/+x"


def squash(text: str) -> str:
    text = _SPACE_RE.sub(" ", text).strip()
    return _LOOSE_PUNCT_RE.sub(lambda m: m.group(1) or m.group(2), text)


_LOOSE_PUNCT_RE = re.compile(r"\s+([,.;:!?/|])|([(\[{])\s+|\s+'(?=\w)")


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    text = text.translate(_TRANSLATE)
    return squash(text)


def fold(text: str) -> str:
    """Lowercase + strip accents: "beyonce" matches "Beyoncé"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return (
        "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()
    )


def trim_edges(text: str) -> str:
    """Drop punctuation/separators hugging either end of a string."""
    return text.strip(_EDGE_CHARS)


def trim_extras(text: str) -> str:
    """Lighter trim for stripped fragments: quotes and parens are kept."""
    return text.strip(_EXTRAS_EDGE)


def dedupe(values) -> list[str]:
    """Tidy + case-insensitively dedupe, keeping first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        value = trim_extras(squash(value))
        key = fold(value)
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


@dataclass(frozen=True)
class Token:
    raw: str
    key: str
    start: int
    end: int


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    for match in _TOKEN_RE.finditer(text):
        raw = match.group()
        core = raw.strip(_EDGE_PUNCT)
        tokens.append(
            Token(raw, fold(core) if core else fold(raw), match.start(), match.end())
        )
    return tokens


def phrase_key(tokens: list[Token]) -> str:
    """Join folded tokens: the lookup form used for ignore words/artists."""
    return " ".join(t.key for t in tokens if t.key)


def read_data_lines(path: Path) -> list[str]:
    """Non-empty, non-comment lines of a data file (missing file -> empty)."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        return []
    out = []
    for line in raw.splitlines():
        line = line.strip().lstrip("\ufeff")
        if line and not line.startswith("#"):
            out.append(line)
    return out


def load_ignore_words(path: Path) -> tuple[set[str], set[tuple[str, ...]]]:
    """``ignore.txt`` -> (junk words, multi-word junk phrases)."""
    words: set[str] = set()
    phrases: set[tuple[str, ...]] = set()
    for line in read_data_lines(path):
        keys = tuple(t.key for t in tokenize(line) if t.key)
        if not keys:
            continue
        if len(keys) == 1:
            words.add(keys[0])
        else:
            phrases.add(keys)
    return words, phrases


def load_artists(path: Path) -> tuple[dict[str, str], set[str]]:
    """``artist.txt`` -> ({"folded phrase": "Display Name"}, {"folded label"}).

    A line starting with ``!`` is a channel or a label rather than a performer.
    Aliases go after a pipe:  ``Alan Walker | Alan W.``
    """
    index: dict[str, str] = {}
    labels: set[str] = set()
    for line in read_data_lines(path):
        is_label = line.startswith("!")
        parts = [p.strip().lstrip("!").strip() for p in line.split("|")]
        if not parts[0]:
            continue
        for name in parts:
            keys = tuple(t.key for t in tokenize(name) if t.key)
            if not keys:
                continue
            index.setdefault(" ".join(keys), parts[0])
            if is_label:
                labels.add(" ".join(keys))
    return index, labels


@dataclass
class Context:
    """The two data files, loaded and indexed for matching."""

    strip_words: set[str]
    soft_words: set[str]
    phrases: set[tuple[str, ...]]
    artists: dict[str, str]
    labels: set[str] = field(default_factory=set)
    problems: list[str] = field(default_factory=list)

    def artist_names(self) -> int:
        return len(set(self.artists.values()) - self.labels)


def build_context(ignore_file: Path, artist_file: Path) -> Context:
    words, phrases = load_ignore_words(ignore_file)
    artists, labels = load_artists(artist_file)
    problems = []
    if not ignore_file.exists():
        problems.append(f"{ignore_file} not found, no junk words loaded")
    if not artist_file.exists():
        problems.append(f"{artist_file} not found, artist names disabled")
    return Context(
        strip_words=words - PROTECTED_WORDS,
        soft_words=words & PROTECTED_WORDS,
        phrases=phrases,
        artists=artists,
        labels=labels,
        problems=problems,
    )


_CONTEXT_CACHE: dict[tuple, Context] = {}


def _mtime(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return -1


def get_context(
    ignore_file: Path = DEFAULT_IGNORE_FILE,
    artist_file: Path = DEFAULT_ARTIST_FILE,
) -> Context:
    """Load both data files; rebuilt automatically when either file changes."""
    key = (str(ignore_file), _mtime(ignore_file), str(artist_file), _mtime(artist_file))
    if key not in _CONTEXT_CACHE:
        _CONTEXT_CACHE.clear()
        _CONTEXT_CACHE[key] = build_context(ignore_file, artist_file)
    return _CONTEXT_CACHE[key]


def junk_kind(token: Token, ctx: Context) -> str | None:
    """ "strip" = always junk, "soft" = junk only inside a run, None = keep."""
    key = token.key
    if not key:
        return None
    if key in ctx.strip_words:
        return "strip"
    if key in ctx.soft_words:
        return "soft"
    if any(rx.fullmatch(key) for rx in _TECH_RES):
        return "strip"
    return None


def is_phrase(tokens: list[Token], ctx: Context) -> bool:
    """True when the tokens spell a multi-word entry of ignore.txt."""
    return bool(tokens) and tuple(t.key for t in tokens) in ctx.phrases


@dataclass
class Credit:
    """A "feat. X" / "Prod. Y" / 'from "Album"' note, kept as written."""

    label: str
    name: str
    raw: str
    start: int
    end: int
    indexes: tuple[int, ...]

    @property
    def text(self) -> str:
        return self.raw

    @property
    def is_feature(self) -> bool:
        return fold(self.label).strip(" .,/+&") in _FEATURE_LABELS


def find_credits(
    tokens: list[Token], text: str, ctx: Context, group: bool
) -> list[Credit]:
    """Find credit labels in a chunk and swallow the name that follows."""
    pattern = GROUP_CREDIT_RE if group else FREE_CREDIT_RE
    credits: list[Credit] = []
    used: set[int] = set()
    for index, token in enumerate(tokens):
        if index in used:
            continue
        match = pattern.match(text[token.start :])
        if not match:
            continue
        label = squash(match.group(1))
        name_from = token.start + match.end(1) + _gap(match.group(0))
        indexes = _swallow_name(tokens, index, name_from, ctx, used)
        if not indexes:
            continue
        first, last = tokens[indexes[0]], tokens[indexes[-1]]
        credits.append(
            Credit(
                label=label,
                name=squash(text[first.start : last.end]),
                raw=squash(text[token.start : last.end]),
                start=token.start,
                end=last.end,
                indexes=tuple(indexes),
            )
        )
        used.update(indexes)
        used.add(index)
    return credits


def _gap(label_match: str) -> int:
    return len(label_match) - len(label_match.lstrip())


def _swallow_name(
    tokens: list[Token], label_index: int, name_from: int, ctx: Context, used: set[int]
) -> list[int]:
    """Indexes of the credit's name: <=6 tokens, stopping at junk or keywords."""
    indexes: list[int] = []
    for index in range(label_index + 1, len(tokens)):
        if len(indexes) >= 6:
            break
        token = tokens[index]
        if index in used or not token.key or token.start < name_from:
            continue
        if junk_kind(token, ctx) or is_phrase([token], ctx):
            break
        if FREE_CREDIT_RE.match(token.raw) or GROUP_CREDIT_RE.match(token.raw):
            break
        indexes.append(index)
    return indexes


@dataclass
class Segment:
    """One piece of a title after junk stripping."""

    raw: str = ""
    residue: str = ""
    offset: int = 0
    extras: list[tuple[int, str]] = field(default_factory=list)
    credits: list[Credit] = field(default_factory=list)


def chunk_text(text: str) -> list[tuple[bool, str, int, str]]:
    """Split into (is_group, raw, offset, inner) chunks, brackets respected."""
    chunks: list[tuple[bool, str, int, str]] = []
    buf: list[str] = []
    buf_start = 0
    index, size = 0, len(text)
    while index < size:
        char = text[index]
        if char in _BRACKETS:
            close = _BRACKETS[char]
            depth, scan = 1, index + 1
            while scan < size and depth:
                if text[scan] == char:
                    depth += 1
                elif text[scan] == close:
                    depth -= 1
                scan += 1
            if depth == 0:
                chunks.append((False, "".join(buf), buf_start, ""))
                chunks.append(
                    (True, text[index:scan], index, text[index + 1 : scan - 1])
                )
                buf, buf_start, index = [], scan, scan
                continue
            buf.append(char)  # unbalanced opener -> plain text
        elif char not in _CLOSERS:
            if not buf:
                buf_start = index
            buf.append(char)
        index += 1  # stray closer -> dropped
    chunks.append((False, "".join(buf), buf_start, ""))
    return chunks


def split_separators(text: str, offset: int) -> list[tuple[str, int]]:
    """Split a plain chunk on " - ", pipes and bullets -> [(piece, offset)]."""
    pieces: list[tuple[str, int]] = []
    cursor = 0
    for match in _SPLIT_RE.finditer(text):
        piece = text[cursor : match.start()]
        if piece.strip():
            pieces.append((piece, offset + cursor))
        cursor = match.end()
    tail = text[cursor:]
    if tail.strip():
        pieces.append((tail, offset + cursor))
    return pieces or [(text, offset)]


def record_extra(segment: Segment, text: str, position: int) -> None:
    """Remember a stripped fragment together with where it came from."""
    text = trim_extras(squash(text))
    if text:
        segment.extras.append((position, text))


def is_track_number(raw: str) -> bool:
    """Leading "01." or "(12)" style numbering, but not the "7" of 7 rings."""
    body = raw.strip(_EDGE_PUNCT)
    if not body.isdigit():
        return False
    if raw.rstrip()[-1:] in ".)":  # "01." / "01)"
        return True
    return len(body) > 1 and body[0] == "0"  # "01", "007"


def drop_numeric_junk(
    tokens: list[Token],
    live: list[int],
    segment: Segment,
    text: str,
    offset: int,
    alone: bool,
) -> list[int]:
    """Drop durations, stray years and a leading track number."""
    kept: list[int] = []
    for position, index in enumerate(live):
        token, key = tokens[index], tokens[index].key
        drop = any(rx.fullmatch(key) for rx in _TECH_RES)
        if not drop and _YEAR_RE.fullmatch(key) and (len(live) > 1 or not alone):
            # "2019" between chunks is the upload year; on its own it is a title
            drop = True
        if not drop and position == 0 and len(live) > 1 and is_track_number(token.raw):
            drop = True  # leading "01."
        if drop:
            record_extra(segment, token.raw, offset + token.start)
        else:
            kept.append(index)
    return kept


def drop_strippable(
    tokens: list[Token],
    live: list[int],
    segment: Segment,
    text: str,
    offset: int,
    ctx: Context,
) -> list[int]:
    """Remove junk words/phrases wherever they sit inside a chunk."""
    kept: list[int] = []
    position = 0
    while position < len(live):
        size = 0
        for candidate in range(min(6, len(live) - position), 1, -1):
            if is_phrase(
                [tokens[i] for i in live[position : position + candidate]], ctx
            ):
                size = candidate
                break
        if not size and junk_kind(tokens[live[position]], ctx) == "strip":
            size = 1
        if size:
            cut = [tokens[i] for i in live[position : position + size]]
            record_extra(
                segment, text[cut[0].start : cut[-1].end], offset + cut[0].start
            )
        else:
            kept.append(live[position])
            size = 1
        position += size
    return kept


def soft_run(
    live: list[int], tokens: list[Token], ctx: Context, from_left: bool
) -> tuple[int, int] | None:
    """Longest edge run of soft junk words (needs 2+ words to be removed)."""
    order = live if from_left else list(reversed(live))
    run = 0
    for index in order:
        if junk_kind(tokens[index], ctx) != "soft" or is_phrase([tokens[index]], ctx):
            break
        run += 1
    if run < 2:
        return None
    return (0, run) if from_left else (len(live) - run, len(live))


def trim_soft_runs(
    tokens: list[Token],
    live: list[int],
    segment: Segment,
    text: str,
    offset: int,
    ctx: Context,
) -> list[int]:
    """Strip soft junk from both edges while an edge run has 2+ words."""
    while live:
        run = soft_run(live, tokens, ctx, True) or soft_run(live, tokens, ctx, False)
        if not run:
            return live
        cut = [tokens[i] for i in live[run[0] : run[1]]]
        record_extra(segment, text[cut[0].start : cut[-1].end], offset + cut[0].start)
        live = live[: run[0]] + live[run[1] :]


def process_text(text: str, ctx: Context, offset: int, alone: bool = True) -> Segment:
    """Turn a plain chunk into a Segment (junk out, credits aside).

    ``alone`` says whether this chunk is the whole title, which decides if a
    bare year ("1989") is a song title or just the upload year.
    """
    segment = Segment(raw=text, offset=offset)
    tokens = tokenize(text)
    if not tokens:
        return segment

    credits = find_credits(tokens, text, ctx, group=False)
    taken = {i for credit in credits for i in credit.indexes}
    for credit in credits:
        taken.add(
            next((i for i, t in enumerate(tokens) if t.start == credit.start), -1)
        )
    live = [i for i in range(len(tokens)) if i not in taken]
    live = drop_numeric_junk(tokens, live, segment, text, offset, alone)
    live = drop_strippable(tokens, live, segment, text, offset, ctx)
    live = trim_soft_runs(tokens, live, segment, text, offset, ctx)

    segment.credits = credits
    if live:
        segment.residue = trim_edges(
            squash(text[tokens[live[0]].start : tokens[live[-1]].end])
        )
    return segment


def chunk_is_junk(tokens: list[Token], ctx: Context) -> bool:
    """Is the whole bracketed chunk metadata, e.g. "(4K Official Music Video)"?

    Phrases from ignore.txt are matched greedily and longest first, so
    "Audio Only" or "Color Coded Lyrics" count as one junk unit.
    """
    covered, index = 0, 0
    while index < len(tokens):
        size = 0
        for candidate in range(min(6, len(tokens) - index), 1, -1):
            if is_phrase(tokens[index : index + candidate], ctx):
                size = candidate
                break
        if size:
            index += size
            covered += size
            continue
        if is_junk_token(tokens[index], ctx):
            index += 1
            covered += 1
            continue
        return False  # a word that could be part of a title
    return covered > 0


def is_junk_token(token: Token, ctx: Context) -> bool:
    """Token is metadata on its own (word from ignore.txt or a tech token)."""
    if junk_kind(token, ctx) or token.key in VERSION_WORDS:
        return True
    if _YEAR_RE.fullmatch(token.key):
        return True
    return any(rx.fullmatch(token.key) for rx in _TECH_RES)


def process_group(inner: str, ctx: Context, offset: int) -> Segment:
    """A bracketed chunk is metadata (extra/credit) or real title text.

    Chunks holding a pipe are joined, since "A | B" inside brackets means
    two separate pieces of junk ("(Lyrics | Color Coded Lyrics)").
    """
    segment = Segment(raw=inner, offset=offset)
    text = squash(inner)
    if not text:
        return segment

    pieces = split_separators(text, offset)
    if len(pieces) > 1:
        joined = []
        for piece, piece_offset in pieces:
            sub = process_group(piece, ctx, piece_offset)
            joined.extend(sub.extras)
            joined.extend(
                (pos, credit.text)
                for pos, credit in [(credit.start, credit) for credit in sub.credits]
            )
            if sub.residue:
                segment.residue = squash(f"{segment.residue} {sub.residue}")
        segment.extras = joined
        return segment

    credits = find_credits(tokenize(text), text, ctx, group=True)
    if credits:
        segment.credits = credits
        return segment

    tokens = tokenize(text)
    if tokens and chunk_is_junk(tokens, ctx):
        record_extra(segment, text, offset)
        return segment
    segment.residue = trim_edges(text)
    return segment


def build_segments(text: str, ctx: Context) -> list[Segment]:
    """Walk the whole title and return its segments in reading order."""
    chunks = chunk_text(text)
    pieces: list[tuple[bool, str, int, str]] = []
    for is_group, raw, offset, inner in chunks:
        if is_group:
            pieces.append((True, raw, offset, inner))
            continue
        for piece, piece_offset in split_separators(raw, offset):
            pieces.append((False, piece, piece_offset, ""))

    plain = sum(1 for is_group, *_ in pieces if not is_group)
    segments: list[Segment] = []
    for is_group, raw, offset, inner in pieces:
        if is_group:
            segments.append(process_group(inner, ctx, offset))
        else:
            segments.append(process_text(raw, ctx, offset, alone=plain == 1))
    return segments


def is_name_token(token: Token, ctx: Context) -> bool:
    if not token.key or junk_kind(token, ctx) or any(c.isdigit() for c in token.raw):
        return False
    return token.raw[:1].isupper() or bool(ctx.artists.get(token.key))


def absorb_collabs(tokens: list[Token], start: int, ctx: Context) -> tuple[str, int]:

    parts: list[str] = []
    index = start
    # "Jubin Nautiyal, Badshah": the matched name has no comma of its own
    if start > 0 and tokens[start - 1].raw.endswith(","):
        parts.append(",")
    joined = start > 0 and is_collab_token(tokens[start - 1])
    for _ in range(4):  # at most 3 extra collaborators
        if not joined:
            if index >= len(tokens) or not is_collab_token(tokens[index]):
                break
            parts.append(tokens[index].raw)
            index += 1
            joined = True
        size = 0
        for candidate in range(min(3, len(tokens) - index), 0, -1):
            if ctx.artists.get(phrase_key(tokens[index : index + candidate])):
                size = candidate
                break
        if not size:
            size = 1 if index < len(tokens) and is_name_token(tokens[index], ctx) else 0
        if not size:
            break
        parts += [token.raw for token in tokens[index : index + size]]
        index += size
        joined = False
    return squash(" ".join(parts)), index


def find_artist(core: list[Segment], ctx: Context) -> dict | None:
    """Best artist.txt match inside the kept chunks: earliest, then longest."""
    best: dict | None = None
    for order, segment in enumerate(core):
        tokens = tokenize(segment.residue)
        # a match that fills the whole chunk is the safest of all
        exact = ctx.artists.get(phrase_key(tokens))
        for start in range(len(tokens)):
            if start > 2:  # an artist never hides behind 3+ words
                break
            for size in range(min(6, len(tokens) - start), 0, -1):
                display = ctx.artists.get(phrase_key(tokens[start : start + size]))
                if display:
                    whole = display == exact

                    score = (0 if whole else 1, start, order, -size)
                    if best is None or score < best["score"]:
                        best = {
                            "score": score,
                            "segment": segment,
                            "tokens": tokens,
                            "start": start,
                            "end": start + size,
                            "display": display,
                        }
                    break
    return best


def looks_like_artist(text: str, ctx: Context) -> bool:
    """Heuristic: short, capitalised, no digits, no leftover junk."""
    tokens = [t for t in tokenize(text) if t.key]
    if not tokens or len(tokens) > 6:
        return False
    if any(any(c.isdigit() for c in token.raw) for token in tokens):
        return False
    if not any(char.isupper() for char in text):
        return False
    return not any(junk_kind(token, ctx) for token in tokens)


def artist_from_collab_only(segments: list[Segment], ctx: Context) -> str:
    """Title is only a "(feat. X)" chunk: use X if artist.txt knows them."""
    for segment in segments:
        for credit in segment.credits:
            display = ctx.artists.get(phrase_key(tokenize(credit.name)))
            if display:
                return display
    return ""


def split_by_credit(segment: Segment, ctx: Context) -> tuple[str, str] | None:
    """ "Song by Artist" -> ("Song", "Artist")."""
    text = segment.residue
    tokens = tokenize(text)
    for position, token in enumerate(tokens[:-1]):
        if fold(token.raw) != "by":
            continue
        left = trim_edges(squash(text[: token.start]))
        right = trim_edges(squash(text[tokens[position + 1].start :]))
        if not left or not right:
            continue
        if looks_like_artist(right, ctx) or phrase_key(tokenize(right)) in ctx.artists:
            return left, right
    return None


def parse_title(raw: str, ctx: Context | None = None, explain: bool = False) -> dict:
    """Raw YouTube title -> ``{"artist": str, "title": str, "extras": list[str]}``."""
    ctx = ctx if ctx is not None else get_context()
    text = clean_text(raw)
    if not text:
        return {"artist": "", "title": "", "extras": []}
    result = _parse_title(text, ctx, explain)
    return result


def is_label_chunk(segment: Segment, ctx: Context) -> bool:
    """True when a chunk is exactly a channel / label from artist.txt."""
    keys = tuple(t.key for t in tokenize(segment.residue) if t.key)
    return bool(keys) and " ".join(keys) in ctx.labels


def _parse_title(text: str, ctx: Context, explain: bool) -> dict:
    segments = build_segments(text, ctx)
    core = [segment for segment in segments if segment.residue]
    extras = [item for segment in segments for item in segment.extras]

    artist, artist_segment, notes = "", None, []
    title_parts: list[tuple[Segment, str]] = []  # (chunk it came from, text)
    title_outside = False  # did any title word come from another chunk?

    hit = find_artist(core, ctx)
    if hit is not None:
        segment, tokens = hit["segment"], hit["tokens"]
        collab, tail_start = absorb_collabs(tokens, hit["end"], ctx)
        artist = squash(f"{hit['display']} {collab}" if collab else hit["display"])
        artist_segment = segment
        head = trim_edges(squash(segment.residue[: tokens[hit["start"]].start]))
        tail = trim_edges(squash(segment.residue[tokens[tail_start - 1].end :]))
        title_parts = [(segment, part) for part in (head, tail) if part]
        title_parts += [
            (other, other.residue) for other in core if other is not segment
        ]
        notes.append(
            f"artist: artist.txt matched {hit['display']!r} in chunk {core.index(segment)}"
        )
    elif len(core) >= 2 and looks_like_artist(core[0].residue, ctx):
        artist, artist_segment = core[0].residue, core[0]
        title_parts = [(other, other.residue) for other in core[1:]]
        notes.append("artist: guessed from the first chunk")
    else:
        for segment in core:
            pair = split_by_credit(segment, ctx)
            if pair:
                left, right = pair
                artist, artist_segment = right, segment
                title_parts = [(segment, left)] + [
                    (s, s.residue) for s in core if s is not segment
                ]
                notes.append("artist: taken from a '... by ...' credit")
                break
        if not artist and len(core) >= 2:
            last = core[-1]
            if len(last.residue.split()) <= 3 and looks_like_artist(last.residue, ctx):
                artist, artist_segment = last.residue, last
                title_parts = [(s, s.residue) for s in core[:-1]]
                notes.append("artist: guessed from the last chunk")
        if not artist and not core:
            artist = artist_from_collab_only(segments, ctx)

    # a channel name sitting in its own chunk is never part of the title:
    # "Kesariya - Arijit Singh | T-Series | 2023" -> T-Series is an extra
    kept_parts: list[tuple[Segment, str]] = []
    for segment, part in title_parts:
        if segment is not artist_segment and is_label_chunk(segment, ctx):
            extras.append((segment.offset, part))
            notes.append(f"extra: {part!r} is a channel, not title text")
        else:
            kept_parts.append((segment, part))
    title_parts = kept_parts
    title_outside = any(segment is not artist_segment for segment, _ in title_parts)

    for segment in segments:
        for credit in segment.credits:
            if segment is artist_segment:
                continue
            same = fold(credit.name) == fold(artist)
            if credit.is_feature and artist and not same:
                artist = squash(f"{artist} {credit.text}")
            elif not artist and len(core) <= 1:
                # "Some Song feat. Someone" -> the credited name is the artist
                guess = ctx.artists.get(phrase_key(tokenize(credit.name)))
                if guess:
                    artist = guess
                    artist_segment = segment
            else:
                extras.append((credit.start, credit.text))

    title = trim_edges(squash(" ".join(part for _, part in title_parts if part)))
    if not title and core and not artist:
        title = trim_edges(squash(" ".join(segment.residue for segment in core)))
    if title and artist and fold(title) == fold(artist) and not title_outside:
        title = ""
    if not title and not artist:
        fallback = max(
            (s for s in segments if s.raw.strip()),
            key=lambda s: len(s.raw),
            default=None,
        )
        if fallback is not None:
            title = trim_edges(squash(fallback.raw))
            extras = []
            notes.append("title: nothing survived, fell back to the raw chunk")

    result = {
        "artist": artist,
        "title": title,
        "extras": dedupe(text for _, text in sorted(extras)),
    }
    if explain:
        result["debug"] = notes + [
            "chunks: " + " | ".join(repr(s.raw) for s in segments if s.raw.strip()),
            "core:   " + " | ".join(repr(s.residue) for s in core),
        ]
    return result
