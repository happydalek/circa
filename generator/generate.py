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
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
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
INK = colors.black
QR_RING_COLORS = [
    "#f3c43f",
    "#ed1e79",
    "#22a7d8",
    "#54c8c4",
    "#7c3c98",
]
ANSWER_PALETTES = [
    ("#f3c85e", "#eba45b"),
    ("#c64d83", "#d96c9a"),
    ("#d95e68", "#e57f63"),
    ("#efbd62", "#e9985f"),
    ("#765793", "#9472a5"),
    ("#42a8c3", "#6ac0cf"),
    ("#8acbc4", "#67b8c1"),
]


def _register_fonts() -> tuple[str, str, str, str]:
    candidates = [
        (
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path(r"C:\Windows\Fonts\arialbd.ttf"),
            Path(r"C:\Windows\Fonts\ariali.ttf"),
            Path(r"C:\Windows\Fonts\arialbi.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"),
        ),
        (
            Path("/Library/Fonts/Arial.ttf"),
            Path("/Library/Fonts/Arial Bold.ttf"),
            Path("/Library/Fonts/Arial Italic.ttf"),
            Path("/Library/Fonts/Arial Bold Italic.ttf"),
        ),
    ]
    for regular_path, bold_path, italic_path, bold_italic_path in candidates:
        font_paths = (regular_path, bold_path, italic_path, bold_italic_path)
        if all(p.exists() for p in font_paths):
            try:
                pdfmetrics.registerFont(TTFont("HitsterRegular", str(regular_path)))
                pdfmetrics.registerFont(TTFont("HitsterBold", str(bold_path)))
                pdfmetrics.registerFont(TTFont("HitsterItalic", str(italic_path)))
                pdfmetrics.registerFont(
                    TTFont("HitsterBoldItalic", str(bold_italic_path))
                )
                return (
                    "HitsterRegular",
                    "HitsterBold",
                    "HitsterItalic",
                    "HitsterBoldItalic",
                )
            except Exception:
                pass
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"


FONT_REGULAR, FONT_BOLD, FONT_ITALIC, FONT_BOLD_ITALIC = _register_fonts()


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


def _color_at(start_hex: str, end_hex: str, t: float) -> colors.Color:
    start = colors.HexColor(start_hex)
    end = colors.HexColor(end_hex)
    return colors.Color(
        start.red + (end.red - start.red) * t,
        start.green + (end.green - start.green) * t,
        start.blue + (end.blue - start.blue) * t,
    )


def _answer_palette(num: int) -> tuple[str, str]:
    return ANSWER_PALETTES[(num - 1) % len(ANSWER_PALETTES)]


def _diagonal_gradient(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    start_hex: str,
    end_hex: str,
) -> None:
    c.saveState()
    clip = c.beginPath()
    clip.rect(x, y, w, h)
    c.clipPath(clip, stroke=0, fill=0)

    steps = 160
    span = w + h
    strip_w = span / steps
    start_x = x - h
    for i in range(steps):
        sx = start_x + i * strip_w
        path = c.beginPath()
        path.moveTo(sx, y)
        path.lineTo(sx + strip_w + 0.8, y)
        path.lineTo(sx + strip_w + h + 0.8, y + h)
        path.lineTo(sx + h, y + h)
        path.close()
        c.setFillColor(_color_at(start_hex, end_hex, i / (steps - 1)))
        c.drawPath(path, fill=1, stroke=0)
    c.restoreState()


def _fit_single_line(
    c: canvas.Canvas,
    text: str,
    font: str,
    size: float,
    min_size: float,
    max_w: float,
) -> tuple[str, float]:
    line = " ".join(str(text).split()) or "-"
    current_size = size
    while current_size >= min_size:
        if c.stringWidth(line, font, current_size) <= max_w:
            return line, current_size
        current_size -= 0.25
    return _ellipsize(c, line, font, min_size, max_w), min_size


def _wrap_words(c: canvas.Canvas, text: str, font: str, size: float, max_w: float) -> list[str]:
    words = " ".join(str(text).split()).split()
    if not words:
        return ["-"]

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or c.stringWidth(candidate, font, size) <= max_w:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_text_block(
    c: canvas.Canvas,
    text: str,
    font: str,
    size: float,
    min_size: float,
    max_w: float,
    max_lines: int,
) -> tuple[list[str], float]:
    current_size = size
    while current_size >= min_size:
        lines = _wrap_words(c, text, font, current_size, max_w)
        if len(lines) <= max_lines:
            return lines, current_size
        current_size -= 0.25

    lines = _wrap_words(c, text, font, min_size, max_w)
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [" ".join(lines[max_lines - 1:])]
    return [
        line
        if c.stringWidth(line, font, min_size) <= max_w
        else _ellipsize(c, line, font, min_size, max_w)
        for line in lines
    ], min_size


def _draw_centered_lines(
    c: canvas.Canvas,
    lines: list[str],
    font: str,
    size: float,
    cx: float,
    center_y: float,
    leading: float,
) -> None:
    c.setFont(font, size)
    first_y = center_y + (len(lines) - 1) * leading / 2
    for i, line in enumerate(lines):
        c.drawCentredString(cx, first_y - i * leading, line)


def _draw_optically_centered(
    c: canvas.Canvas,
    text: str,
    font: str,
    size: float,
    cx: float,
    center_y: float,
) -> None:
    ascent = pdfmetrics.getAscent(font, size)
    descent = pdfmetrics.getDescent(font, size)
    baseline_y = center_y - (ascent + descent) / 2
    c.setFont(font, size)
    c.drawCentredString(cx, baseline_y, text)


def _draw_front(c: canvas.Canvas, idx: int, qr: ImageReader, num: int) -> None:
    x, y = front_origin(idx)

    c.setFillColor(INK)
    c.rect(x, y, CARD_W, CARD_H, fill=1, stroke=0)

    cx = x + CARD_W / 2
    cy = y + CARD_H / 2

    ring_radii = [25.4 * mm, 23.1 * mm, 20.9 * mm, 18.6 * mm, 16.4 * mm]
    for ring_idx, radius in enumerate(ring_radii):
        ring_color = QR_RING_COLORS[(num + ring_idx) % len(QR_RING_COLORS)]
        c.setStrokeColor(colors.HexColor(ring_color))
        c.setLineWidth(0.55)
        c.circle(cx, cy, radius, fill=0, stroke=1)

    qr_size = CARD_W * 0.48
    qr_x = x + (CARD_W - qr_size) / 2
    qr_y = cy - qr_size / 2
    c.drawImage(qr, qr_x, qr_y, qr_size, qr_size, mask="auto")

    _crop_marks(c, x, y)


def _ellipsize(c: canvas.Canvas, text: str, font: str, size: float, max_w: float) -> str:
    suffix = "..."
    text = str(text).strip()
    while text and c.stringWidth(text + suffix, font, size) > max_w:
        text = text[:-1].rstrip()
    return text + suffix if text else suffix


def _draw_back(c: canvas.Canvas, idx: int, song: dict, num: int) -> None:
    x, y = back_origin(idx)

    start_color, end_color = _answer_palette(num)
    _diagonal_gradient(c, x, y, CARD_W, CARD_H, start_color, end_color)

    cx = x + CARD_W / 2
    max_w = CARD_W - 7 * mm

    artist_lines, artist_size = _fit_text_block(
        c, song["artist"], FONT_BOLD, 13.0, 6.0, max_w, 2
    )
    c.setFillColor(INK)
    _draw_centered_lines(
        c,
        artist_lines,
        FONT_BOLD,
        artist_size,
        cx,
        y + CARD_H - 11.0 * mm,
        artist_size + 2.0,
    )

    year = str(song["year"]).strip()
    _draw_optically_centered(c, year, FONT_BOLD_ITALIC, 48, cx, y + CARD_H / 2)

    title_lines, title_size = _fit_text_block(
        c, song["title"], FONT_ITALIC, 13.0, 6.0, max_w, 2
    )
    _draw_centered_lines(
        c,
        title_lines,
        FONT_ITALIC,
        title_size,
        cx,
        y + 13.6 * mm,
        title_size + 2.0,
    )

    _crop_marks(c, x, y)


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
    parser = argparse.ArgumentParser(description="Generate Hitster Card Maker PDF")
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
        help="Directory for caching fetched playlist data (default: ~/.cache/hitster-card-maker)",
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
