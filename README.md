# Circa

A board game where each card has a QR code on one side and song metadata (title, artist, year) on the other. Scanning the QR opens a phone app that plays the song **without revealing what it is** — players guess the year (and artist/title if they dare), then flip the card to check.

## Components

- **`app/`** — installable PWA. Scans QR codes with the phone camera, then plays the linked song through a YouTube IFrame player with an opaque cover UI hiding title, thumbnail, and channel until the players are ready.
- **`generator/`** — Python script that reads a curated song CSV and produces a print-ready PDF of cards (QR front, metadata back, duplex-aligned for a standard A4 home printer).
- **`songs/songs.csv`** — the curated song list. Columns: `youtube_id,title,artist,year`.

## Quickstart

**App (local dev):**
```bash
cd app && npm install && npm run dev -- --host
```

**Card generator:**
```bash
cd generator
uv run generate.py --csv ../songs/songs.csv --out cards.pdf
```

Print `cards.pdf` duplex (long-edge flip), cut along the crop marks, and play.
