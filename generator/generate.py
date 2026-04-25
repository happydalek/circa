#!/usr/bin/env python3
"""Generate printable card PDF from a playlist or CSV.

Usage:
    # From a YouTube Music or Spotify playlist (blind — you won't see song names):
    uv run generate.py --playlist "https://open.spotify.com/playlist/<id>" --out cards.pdf
    uv run generate.py --playlist "https://music.youtube.com/playlist?list=<id>" --out cards.pdf

    # Mix multiple playlists, deduplicated:
    uv run generate.py --playlist URL1 --playlist URL2 --out cards.pdf

    # From hand-curated CSV (still works):
    uv run generate.py --csv ../songs/songs.csv --out cards.pdf
"""

import argparse
import csv
import io
import sys
from pathlib import Path

try:
    import qrcode
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
except ImportError as e:
    sys.exit(f"Missing dependency: {e}\nRun: pip install -r requirements.txt")

from layout import (
    PAGE_W, PAGE_H, CARD_W, CARD_H, COLS, ROWS,
    front_origin, back_origin,
)

CROP_LEN = 3 * mm
CROP_GAP = 1 * mm
CARDS_PER_PAGE = COLS * ROWS


def _make_qr(data: str) -> ImageReader:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _crop_marks(c: canvas.Canvas, x: float, y: float) -> None:
    c.setStrokeColor(colors.lightgrey)
    c.setLineWidth(0.3)
    offsets = [
        # (corner_x, corner_y, h_dir, v_dir)
        (x,          y,          1,  1),
        (x + CARD_W, y,         -1,  1),
        (x + CARD_W, y + CARD_H,-1, -1),
        (x,          y + CARD_H, 1, -1),
    ]
    for cx, cy, hd, vd in offsets:
        c.line(cx + hd * CROP_GAP, cy, cx + hd * (CROP_GAP + CROP_LEN), cy)
        c.line(cx, cy + vd * CROP_GAP, cx, cy + vd * (CROP_GAP + CROP_LEN))


def _draw_front(c: canvas.Canvas, idx: int, qr: ImageReader, num: int) -> None:
    x, y = front_origin(idx)
    _crop_marks(c, x, y)

    c.setFillColor(colors.white)
    c.rect(x, y, CARD_W, CARD_H, fill=1, stroke=0)

    qr_size = min(CARD_W, CARD_H) * 0.78
    qr_x = x + (CARD_W - qr_size) / 2
    qr_y = y + (CARD_H - qr_size) / 2 + 3 * mm
    c.drawImage(qr, qr_x, qr_y, qr_size, qr_size, mask="auto")

    c.setFillColor(colors.lightgrey)
    c.setFont("Helvetica", 6)
    c.drawRightString(x + CARD_W - 2 * mm, y + 2 * mm, str(num))


def _fit_string(c: canvas.Canvas, text: str, font: str, size: float, max_w: float) -> str:
    while c.stringWidth(text, font, size) > max_w and len(text) > 6:
        text = text[:-4] + "\u2026"
    return text


def _draw_back(c: canvas.Canvas, idx: int, song: dict, num: int) -> None:
    x, y = back_origin(idx)
    _crop_marks(c, x, y)

    c.setFillColor(colors.HexColor("#1a1a2e"))
    c.rect(x, y, CARD_W, CARD_H, fill=1, stroke=0)

    cx = x + CARD_W / 2
    max_w = CARD_W - 8 * mm

    # Year
    c.setFillColor(colors.HexColor("#e63946"))
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(cx, y + CARD_H * 0.57, song["year"])

    # Divider
    c.setStrokeColor(colors.HexColor("#2a2a4e"))
    c.setLineWidth(0.5)
    c.line(x + 8 * mm, y + CARD_H * 0.52, x + CARD_W - 8 * mm, y + CARD_H * 0.52)

    # Title
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    title = _fit_string(c, song["title"], "Helvetica-Bold", 11, max_w)
    c.drawCentredString(cx, y + CARD_H * 0.38, title)

    # Artist
    c.setFillColor(colors.HexColor("#9ca3af"))
    c.setFont("Helvetica", 9)
    artist = _fit_string(c, song["artist"], "Helvetica", 9, max_w)
    c.drawCentredString(cx, y + CARD_H * 0.28, artist)

    # Card number
    c.setFillColor(colors.HexColor("#3a3a5e"))
    c.setFont("Helvetica", 6)
    c.drawRightString(x + CARD_W - 2 * mm, y + 2 * mm, str(num))


def generate(songs: list[dict], out_path: Path, base_url: str) -> None:
    if not base_url.endswith("/"):
        base_url += "/"

    if not songs:
        sys.exit("No songs to generate.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=(PAGE_W, PAGE_H))

    num_sheets = (len(songs) - 1) // CARDS_PER_PAGE + 1

    for sheet in range(num_sheets):
        chunk = songs[sheet * CARDS_PER_PAGE: (sheet + 1) * CARDS_PER_PAGE]

        # Front page
        for idx, song in enumerate(chunk):
            num = sheet * CARDS_PER_PAGE + idx + 1
            qr = _make_qr(f"{base_url}#/play?v={song['youtube_id']}")
            _draw_front(c, idx, qr, num)
        c.showPage()

        # Back page
        for idx, song in enumerate(chunk):
            num = sheet * CARDS_PER_PAGE + idx + 1
            _draw_back(c, idx, song, num)
        c.showPage()

    c.save()
    print(f"Done: {out_path}  ({len(songs)} cards, {num_sheets * 2} PDF pages)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Circa card PDF")
    parser.add_argument(
        "--csv", type=Path, default=None,
        help="Path to songs CSV (optional if --playlist is given)",
    )
    parser.add_argument(
        "--playlist", action="append", dest="playlists", metavar="URL", default=[],
        help=(
            "Playlist URL to fetch songs from (repeatable). "
            "Supports YouTube Music, YouTube, and Spotify."
        ),
    )
    parser.add_argument("--out", required=True, type=Path, help="Output PDF path")
    parser.add_argument(
        "--base-url",
        default="https://happydalek.github.io/hitster-card-maker/",
        help="Deployed PWA base URL (default: GitHub Pages URL)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache" / "hitster-card-maker",
        help="Directory for caching fetched playlist data (default: ~/.cache/circa)",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Ignore and overwrite any cached playlist data",
    )
    args = parser.parse_args()

    if not args.csv and not args.playlists:
        parser.error("Provide at least --csv PATH or one --playlist URL.")

    songs: list[dict] = []

    # 1. CSV songs first (hand-curated tracks take precedence on dedup)
    if args.csv:
        with args.csv.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                songs.append({k.strip(): v.strip() for k, v in row.items()})

    # 2. Playlist songs
    if args.playlists:
        from fetcher import fetch_playlist  # local import; only needed when used
        cache_dir = None if args.no_cache else args.cache_dir
        for url in args.playlists:
            songs.extend(fetch_playlist(url, cache_dir))

    # 3. Deduplicate by youtube_id, preserving order (CSV wins on conflict)
    seen: set[str] = set()
    deduped: list[dict] = []
    for song in songs:
        vid = song.get("youtube_id", "")
        if vid and vid not in seen:
            seen.add(vid)
            deduped.append(song)
    songs = deduped

    if not songs:
        sys.exit("No songs found after fetching/deduplication.")

    generate(songs, args.out, args.base_url)


if __name__ == "__main__":
    main()
