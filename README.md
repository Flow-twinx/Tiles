# tile-twinx

Takes a raw YouTube title and splits it into `artist`, `title` and `extras`.

```
$ uv run app.py --json "Marshmello - Alone (Official Music Video)"
{"artist": "Marshmello", "title": "Alone", "extras": ["Official Music Video"]}
```

## Install

```bash
uv add tile-twinx
```

```python
from Tile import parse_title

parse_title("Kesariya - Arijit Singh | T-Series | 2023")
# {'artist': 'Arijit Singh', 'title': 'Kesariya', 'extras': ['T-Series', '2023']}
```

No dependencies, Python 3.12+.

## The demo app

`app.py` runs a list of real YouTube titles through the parser and prints a
table. With no arguments it uses its built-in list of 29 titles:

```bash
uv run app.py                                   # the built-in list
uv run app.py "Alan Walker - Faded"             # one title
uv run app.py --file my_titles.txt              # a file, one title per line
yt-dlp --print "%(title)s" URL | uv run app.py  # straight from yt-dlp
uv run app.py --random 5                        # 5 random ones
uv run app.py --interactive                     # type titles by hand
```

```
  ARTIST  TITLE  EXTRAS
  --------------------------  ----------------------------------  ----------------------
  Marshmello                  Alone                               Official Music Video
  Kesariya                    Kesariya                            Full Song, 4K, 1080p, HD
  Arijit Singh                Kesariya                            T-Series, 2023
  ...

  parsed 29 titles
  artist found 29/29  100%
  extras found 25/29  86%
```

Flags: `--json`, `--dict`, `--explain` (why the parser decided what it did),
`--summary`, `--colour auto|always|never`. `uv run app.py --help` lists them all.

`app.py` doubles as a smoke test: it holds 29 real titles whose expected output
is in the table above, so if a parser change breaks something it shows up
there.

## Library

```python
from Tile import parse_title, get_context

parse_title("Marshmello - Alone (Official Music Video)")
# {'artist': 'Marshmello', 'title': 'Alone', 'extras': ['Official Music Video']}

parse_title(raw, explain=True)        # adds a "debug" list of decision notes
ctx = get_context("~/my-ignore.txt", "~/my-artists.txt")   # your own data files
parse_title(raw, ctx)
```

`Tile` also exports `build_context`, `Context`, `Segment` and `Token` for
anyone poking at the internals. `get_context` caches by mtime and reloads
automatically when a data file changes.

## Files

| Path            | Purpose                                                       |
| --------------- | ------------------------------------------------------------- |
| `main.py`       | the whole engine plus its CLI - still the single source of truth |
| `assets/ignore.txt` | junk words/phrases to strip (`4k`, `lyric`, `official ...`)  |
| `assets/artist.txt` | artist names, `Main Name \| Alias` per line                 |
| `Tile/__init__.py` | the public API, `from Tile import ...`                      |
| `app.py`        | the demo app                                                 |

`main.py` stays in the repo root; the wheel ships that same file as
`Tile/main.py` so it installs inside the package, and `Tile/__init__.py`
supports both layouts. The checkout and an installed copy behave identically.

Both data files are re-read whenever they change, no restart needed. `#`
starts a comment in either one.

## How it decides

1. **Clean** - unescape `&amp;`, normalise unicode, unify dashes and quotes,
   split the title into chunks on ` - `, `|`, `•`.
2. **Brackets** - each `(...)` / `[...]` / `{...}` group is either metadata
   (`(Official Video)`, `(feat. X)`, `(from "Album")`) or real title text
   (`(Humming)`). A group whose every word is junk becomes an extra.
3. **Junk** - `ignore.txt` words go anywhere, except the handful that also start
   or end real titles (`old`, `song`, `video`, `full`, `audio`, ...), which are
   only removed next to other junk. That is what keeps *Old Town Road* and
   *Video Games* intact while *Song 4K* still loses its junk.
4. **Credits** - `feat./ft./prod./cover by/from "..."` are pulled out before
   junk removal, then folded into the artist.
5. **Artist** - the best `artist.txt` match: a chunk that *is* the artist beats
   one that merely contains the name, the earlier chunk beats a later one, and
   within a chunk the longest match wins. It then extends over `x`, `&`, `,`
   and `feat.` collaborators. Without a match it falls back to the first chunk,
   then a `Song by Artist` form, then the last chunk.
6. **Title** - whatever is left, with extras in the order they appeared.

## Adding to the data files

```ini
# ignore.txt - a single word is stripped anywhere, a phrase too
official teaser          # safe anywhere: never part of a title

# artist.txt - aliases after a pipe, matched without case or accents
Alan Walker | Alan W.

# artist.txt - "!" marks a channel or label, never a performer
!Saregama
```

A label in its own chunk becomes an extra, so `Kesariya - Arijit Singh |
T-Series | 2023` gives `Arijit Singh / Kesariya / ["T-Series", "2023"]`, while
`T-Series - Kesariya` still credits T-Series as the artist.

Run `uv run app.py` after editing: it reloads the data files, so a regression
shows up immediately in the table.

## Known limits

- An unspaced dash is never a separator (`Marshmello-Alone-Official` stays one
  word), because `Spider-Man` and `Merry-Go-Round` outnumber the broken form.
- When a title and its artist are both unknown *and* both are short, the first
  chunk is taken as the artist. Adding the name to `assets/artist.txt` fixes
  the whole family of titles at once.

## Publishing

```bash
uv build                                  # dist/*.whl + dist/*.tar.gz
twine check dist/*                        # verify metadata without uploading
uv publish                                # needs a token in ~/.pypirc or UV_PUBLISH_TOKEN
```

Distribution name `tile-twinx`, import name `Tile`.