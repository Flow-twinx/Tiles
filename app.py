#!/usr/bin/env python3
"""A small demo app for the Tile title parser.

Run it with no arguments to parse a built-in list of real YouTube titles:

    uv run app.py

Feed it your own instead, however you like:

    uv run app.py "Marshmello - Alone (Official Music Video)"
    uv run app.py --file my_titles.txt          # one title per line
    yt-dlp --print "%(title)s" URL | uv run app.py
    uv run app.py --interactive                 # type titles one by one

Output:

    --json      one json object per title
    --dict      python dicts, the default library return value
    --explain   show why the parser decided what it did
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import get_context, parse_title

SAMPLE_TITLES: list[str] = [
    "Marshmello - Alone (Official Music Video)",
    "Alan Walker - Faded [4K] (Lyrics)",
    "[Official Music Video] Diljit Dosanjh - Moonchild Era",
    "T-Series - Kesariya (Full Song) [4K] 1080p HD",
    "Kesariya - Arijit Singh | T-Series | 2023",
    "Arijit Singh - Tum Hi Ho (Lyrics)",
    'Shreya Ghoshal - Thodi Der (from "Love Aaj Kal")',
    'Yo Yo Honey Singh - Chaiyya Chaiyya (from "Dil Se") | HD',
    "Badshah - Paani & Saan (feat. Saheer)",
    "Karan Aujla & Tigerstyle - Punjab",
    "Baarish Mein Tera Naam - Mickey Virus Mal (Official Video)",
    'Sonu Nigam - Kal Ho Naa Ho (from "Kal Ho Naa Ho") | HDRip',
    "Kishore Kumar - Mere Samne Wali Khidki (Old Song) [1080p]",
    "Neha Kakkar - Kesariya (Cover)",
    "Shaan - Aankhon Mein Tera Hi Chehra (Full Song) 3:47",
    "Coldplay - Viva La Vida 4K Remastered Official Video",
    "Ed Sheeran - Perfect (Acoustic)",
    "Ed Sheeran & Justin Bieber - I Don't Care (Official Video)",
    "Passenger - Let Her Go (feat. Edith Whiskers) | Official Audio",
    "Billie Eilish - bad guy (Official Music Video) [HD] 4K",
    "Travis Scott - HIGHEST IN THE ROOM (Official Music Video)",
    "Lana Del Rey - Video Games (Official Video)",
    "'TU HI HO' | Arijit Singh | Lyrics | 4K",
    "BLACKPINK - 'BOOMBAYAH' (Official Video)",
    "System of a Down - B.Y.O.B.",
    "Simon & Garfunkel - Bridge Over Troubled Water",
    "Linkin Park - In The End (Official Music Video)",
    "Linkin Park - Somewhere Over The Rainbow (cover)",
    "Some Random Guy - Random Song (Official Video) 4K HD 2021",
]


_ESCAPES = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "grey": "\033[90m",
}

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def use_colour(force: str) -> bool:
    """--colour always/never/auto (auto = only when stdout is a terminal)."""
    if force == "always":
        return True
    if force == "never":
        return False
    return sys.stdout.isatty()


class Paint:
    """Adds ANSI colour, but only when the caller allows it."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def __call__(self, text: str, *styles: str) -> str:
        if not self.enabled or not styles:
            return text
        codes = "".join(_ESCAPES.get(style, "") for style in styles)
        return f"{codes}{text}{_ESCAPES['reset']}"

    @staticmethod
    def width(text: str) -> int:
        """Printable width, ignoring colour codes and counting wide glyphs."""
        plain = _ANSI_RE.sub("", text)
        return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in plain)


def fit(text: str, width: int) -> str:
    """Pad or ellipsise to exactly ``width`` printable columns."""
    if Paint.width(text) <= width:
        return text + " " * (width - Paint.width(text))
    out, used = "", 0
    for ch in text:
        step = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if used + step > width - 1:
            return out + "…"
        out += ch
        used += step
    return out


# ==========================================================================
# output
# ==========================================================================

GREY = ("grey",)
HEAD = ("bold",)


def print_table(results: list[dict], paint: Paint) -> None:
    """One row per title: what the parser made of it."""
    rows = []
    for result in results:
        rows.append(
            (
                fit(result["artist"] or paint("—", *GREY), 30),
                fit(result["title"] or paint("—", *GREY), 60),
                paint(", ".join(result["extras"]), *GREY)
                if result["extras"]
                else paint("—", *GREY),
            )
        )

    print()
    print(
        paint("  ARTIST", *HEAD)
        + "  "
        + paint("TITLE", *HEAD)
        + "  "
        + paint("EXTRAS", *HEAD)
    )
    print(paint("  " + "-" * 30 + "  " + "-" * 60 + "  " + "-" * 22, *GREY))
    for artist, title, extras in rows:
        print(f"  {artist}  {title}  {extras}")
    print()


def print_explain(results: list[dict]) -> None:
    for result in results:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def print_summary(results: list[dict], paint: Paint) -> None:
    """How the batch went, so a bad run is obvious."""
    total = len(results)
    with_artist = sum(1 for r in results if r["artist"])
    with_extras = sum(1 for r in results if r["extras"])
    bare = sum(1 for r in results if not r["artist"] and not r["title"])

    def pct(count: int) -> str:
        return f"{count}/{total}" if total else "0/0"

    print(paint("  parsed", "bold"), f"{total} titles")
    print(
        paint("  artist found", *GREY),
        f"{pct(with_artist)}  {100 * with_artist // max(total, 1)}%",
    )
    print(
        paint("  extras found", *GREY),
        f"{pct(with_extras)}  {100 * with_extras // max(total, 1)}%",
    )
    if bare:
        print(
            paint("  gave up on", "yellow"),
            paint(
                f"{bare} - nothing survived, add the name to assets/artist.txt", *GREY
            ),
        )
    print()


# ==========================================================================
# input
# ==========================================================================


def read_titles(args: argparse.Namespace) -> list[str]:
    """Titles from the command line, a file, stdin, or the sample list."""
    if args.interactive:
        return interactive_titles()

    titles = list(args.titles)
    if args.file:
        path = Path(args.file)
        if not path.exists():
            sys.exit(f"error: {path} not found")
        titles += [
            line.strip() for line in path.read_text().splitlines() if line.strip()
        ]
    if args.stdin or (not titles and not args.file and not sys.stdin.isatty()):
        titles += [
            line.strip() for line in sys.stdin.read().splitlines() if line.strip()
        ]
    if not titles:
        titles = list(SAMPLE_TITLES)
        print(
            f"no titles given, using the built-in list of {len(titles)}",
            file=sys.stderr,
        )
    if args.random:
        titles = random.sample(titles, min(args.random, len(titles)))
    return titles


def interactive_titles(paint: Paint) -> list[str]:
    """Type a title, see the parse, repeat. Blank line or Ctrl-D to stop."""
    titles: list[str] = []
    print()
    print(paint("  paste YouTube titles, one per line. empty line ends it.", *GREY))
    while True:
        try:
            raw = input(paint("  > ", "cyan")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return titles
        if not raw:
            return titles
        titles.append(raw)
        result = parse_title(raw, get_context())
        print(
            f"    {result['artist'] or '—'}  {paint(result['title'] or '—', 'bold')}"
            f"  {paint(', '.join(result['extras']), *GREY)}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="app.py",
        description="Demo app: parse a list of YouTube titles with Tile.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  app.py                                  # the built-in sample list\n"
            '  app.py "Alan Walker - Faded"            # one title\n'
            "  app.py --file titles.txt --json         # a file, as json\n"
            "  app.py --random 5 --explain             # 5 random titles, with reasons\n"
            "  app.py --interactive                    # type titles by hand"
        ),
    )
    parser.add_argument("titles", nargs="*", help="raw YouTube titles")
    parser.add_argument("--file", help="a text file with one title per line")
    parser.add_argument(
        "--stdin", action="store_true", help="also read titles from stdin"
    )
    parser.add_argument(
        "--random", type=int, metavar="N", help="only parse N random titles"
    )
    parser.add_argument(
        "--interactive", action="store_true", help="type titles one by one"
    )
    parser.add_argument("--json", action="store_true", help="print json objects")
    parser.add_argument(
        "--dict", action="store_true", help="print python dicts (default)"
    )
    parser.add_argument(
        "--explain", action="store_true", help="show the parser's reasoning"
    )
    parser.add_argument(
        "--summary", action="store_true", help="print a tally at the end"
    )
    parser.add_argument(
        "--colour",
        choices=("auto", "always", "never"),
        default="auto",
        help="colourise the table (default: auto)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paint = Paint(use_colour(args.colour) and not args.json and not args.dict)

    ctx = get_context()
    for problem in ctx.problems:
        print(f"warning: {problem}", file=sys.stderr)
    if args.interactive:
        interactive_titles(paint)
        return 0

    titles = read_titles(args)
    results = [parse_title(raw, ctx, explain=args.explain) for raw in titles]

    if args.explain:
        print_explain(results)
    elif args.json:
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
    elif args.dict:
        for result in results:
            print(repr(result))
    else:
        print_table(results, paint)

    if args.summary or not (args.json or args.dict or args.explain):
        print_summary(results, paint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
