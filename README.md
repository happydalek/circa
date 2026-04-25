# Hitster Card Maker

Build custom card decks for [Hitster](https://www.hitstergame.com/) from any Spotify or YouTube Music playlist.

Each card has a QR code on one side and the song's year, title, and artist on the other — just like official Hitster cards, but with songs you actually want to play.

## How it works

1. **Pick playlists** — choose any Spotify or YouTube Music playlists without looking at the tracklist.
2. **Generate cards** — the tool fetches the songs, finds YouTube video IDs, and produces a print-ready PDF.
3. **Print & play** — print duplex, cut along the crop marks, shuffle into your Hitster deck (or play standalone).
4. **Scan & listen** — scanning a QR code opens the companion phone app, which plays the song on YouTube with the title/artist hidden until you're ready to reveal.

## Components

- **`app/`** — installable PWA (phone app). Scans QR codes, plays the linked YouTube video behind an opaque cover until players tap Reveal.
- **`generator/`** — fetches songs from Spotify / YouTube Music playlists and produces a print-ready A4 PDF. Has a desktop UI (`ui.py`) and a CLI (`generate.py`).
- **`songs/songs.csv`** — optional hand-curated song list you can mix in. Columns: `youtube_id,title,artist,year`.

## Quickstart

**Phone app (local dev):**
```bash
cd app && npm install && npm run dev -- --host
```

**Card generator — desktop UI (easiest):**
```bash
cd generator && uv run ui.py
```

Paste playlist URLs, pick an output path, click **Generate PDF**. Song titles are never shown during generation so the deck stays a surprise.

**Card generator — CLI:**
```bash
cd generator

# From a Spotify playlist
uv run generate.py --playlist "https://open.spotify.com/playlist/<id>" --out cards.pdf

# From a YouTube Music playlist
uv run generate.py --playlist "https://music.youtube.com/playlist?list=<id>" --out cards.pdf

# Mix multiple playlists (deduplicated automatically)
uv run generate.py --playlist URL1 --playlist URL2 --out cards.pdf

# Mix with a hand-curated CSV
uv run generate.py --csv ../songs/songs.csv --playlist URL1 --out cards.pdf
```

Fetched playlist data is cached in `~/.cache/hitster-card-maker/` so re-runs are instant. Pass `--no-cache` to force a fresh fetch.

Print `cards.pdf` duplex (long-edge flip), cut along the crop marks, and play.

## Notes

- No Spotify API key needed — song metadata is scraped from the public embed page.
- Years are sourced from YouTube Music album data (original release year, not remaster year).
- The phone app is deployed at `https://happydalek.github.io/hitster-card-maker/` via GitHub Actions.
