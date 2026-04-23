# project-not-hitster

A Hitster-style board game where each card has a QR code on one side and song metadata (title, artist, year) on the other. Scanning the QR opens a phone app that plays the song **without revealing what it is** — players guess, then flip the card to check.

## Components

- **`app/`** — installable PWA. Scans QR codes with the phone camera, then plays the linked song through a YouTube IFrame player with an opaque cover UI hiding title, thumbnail, and channel until the players are ready.
- **`generator/`** — Python script that reads a curated song CSV and produces a print-ready PDF of cards (QR front, metadata back, duplex-aligned for a standard A4 home printer).
- **`songs/songs.csv`** — the curated song list. Columns: `youtube_id,title,artist,year`.

## Status

Early scaffolding. See [plan file](../../.claude/plans/we-are-going-to-deep-perlis.md) (local to the machine the repo was created on) for the current design and verification strategy.
