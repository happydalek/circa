"""Fetch song lists from YouTube Music, YouTube, or Spotify playlist URLs.

Verified JSON paths (2026-04-24):
  Spotify embed __NEXT_DATA__: props → pageProps → state → data → entity → trackList
  Each track: {"title": ..., "subtitle": "Artist1,\xa0Artist2", ...}
"""

from __future__ import annotations

import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from ytmusicapi import YTMusic

# Spotify embed __NEXT_DATA__ path — update if the embed page structure changes.
_SPOTIFY_PATH = ["props", "pageProps", "state", "data", "entity", "trackList"]


# ── Public entry point ────────────────────────────────────────────────────────


def fetch_playlist(url: str, cache_dir: Path | None = None) -> list[dict]:
    """Return a list of song dicts from a YouTube Music, YouTube, or Spotify playlist URL.

    Each dict has keys: youtube_id, title, artist, year.
    """
    host = urlparse(url).netloc.lower()
    if "spotify.com" in host:
        return _fetch_spotify(_parse_spotify_id(url), cache_dir)
    elif "youtube.com" in host:
        return _fetch_youtube(_parse_youtube_id(url), cache_dir)
    else:
        sys.exit(
            f"Unsupported playlist URL: {url}\n"
            "Supported hosts: music.youtube.com, youtube.com, open.spotify.com"
        )


# ── URL helpers ───────────────────────────────────────────────────────────────


def _parse_youtube_id(url: str) -> str:
    qs = parse_qs(urlparse(url).query)
    ids = qs.get("list", [])
    if not ids:
        sys.exit(f"Cannot extract playlist ID from YouTube URL: {url}")
    return ids[0]


def _parse_spotify_id(url: str) -> str:
    m = re.search(r"/playlist/([A-Za-z0-9]+)", url)
    if not m:
        sys.exit(f"Cannot extract playlist ID from Spotify URL: {url}")
    return m.group(1)


# ── Cache helpers ─────────────────────────────────────────────────────────────


def _cache_load(cache_dir: Path | None, key: str) -> list[dict] | None:
    if cache_dir is None:
        return None
    p = cache_dir / f"{key}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _cache_save(cache_dir: Path | None, key: str, songs: list[dict]) -> None:
    if cache_dir is None:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(
        json.dumps(songs, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Year + video ID lookup ────────────────────────────────────────────────────


def _search_year_and_id(yt: YTMusic, title: str, artist: str) -> tuple[str, str]:
    """Search YouTube Music for (title, artist).

    Returns (video_id, year). Year comes from get_album() — accurate original
    release year even for remastered/deluxe editions. Returns ("", "") if not found.
    """
    results = yt.search(f"{artist} {title}", filter="songs", limit=1)
    if not results:
        return "", ""

    r = results[0]
    video_id = r.get("videoId", "")

    album = r.get("album") or {}
    album_id = album.get("id")
    year = ""
    if album_id:
        try:
            album_data = yt.get_album(album_id)
            year = str(album_data.get("year") or "")
        except Exception:
            pass

    return video_id, year


# ── YouTube / YouTube Music fetcher ──────────────────────────────────────────


def _fetch_youtube(playlist_id: str, cache_dir: Path | None) -> list[dict]:
    cache_key = f"yt_{playlist_id}"
    cached = _cache_load(cache_dir, cache_key)
    if cached is not None:
        print(f"  [cache] YouTube playlist {playlist_id}: {len(cached)} tracks")
        return cached

    yt = YTMusic()
    print(f"Fetching YouTube Music playlist {playlist_id} ...", flush=True)
    data = yt.get_playlist(playlist_id, limit=None)
    tracks = data.get("tracks", [])
    total = len(tracks)
    skipped = 0

    songs: list[dict] = []

    for i, track in enumerate(tracks, 1):
        print(f"\r  {i}/{total}", end="", flush=True)

        video_id = track.get("videoId")
        if not video_id:
            skipped += 1
            continue

        title = track.get("title", "")
        artists = track.get("artists") or []
        artist = artists[0]["name"] if artists else "Unknown"

        # Year is not set on playlist tracks; search to find album year.
        _, year = _search_year_and_id(yt, title, artist)
        time.sleep(0.15)  # gentle rate limiting between tracks

        songs.append({
            "youtube_id": video_id,
            "title": title,
            "artist": artist,
            "year": year,
        })

    print()  # end progress line

    if skipped:
        print(f"  {skipped} unavailable track(s) skipped.")

    _cache_save(cache_dir, cache_key, songs)
    return songs


# ── Spotify fetcher ───────────────────────────────────────────────────────────


class _NextDataParser(HTMLParser):
    """Extract JSON content of <script id="__NEXT_DATA__">."""

    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self.json_text = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self._capture = True

    def handle_data(self, data: str) -> None:
        if self._capture:
            self.json_text = data
            self._capture = False


def _get_nested(obj: dict, path: list[str]):
    """Walk a nested dict along path; return None if any key is missing."""
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


def _fetch_spotify(playlist_id: str, cache_dir: Path | None) -> list[dict]:
    cache_key = f"sp_{playlist_id}"
    cached = _cache_load(cache_dir, cache_key)
    if cached is not None:
        print(f"  [cache] Spotify playlist {playlist_id}: {len(cached)} tracks")
        return cached

    embed_url = (
        f"https://open.spotify.com/embed/playlist/{playlist_id}?utm_source=generator"
    )
    print(f"Fetching Spotify playlist {playlist_id} ...", flush=True)
    resp = requests.get(
        embed_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
        timeout=15,
    )
    resp.raise_for_status()

    parser = _NextDataParser()
    parser.feed(resp.text)
    if not parser.json_text:
        sys.exit(
            "Could not find __NEXT_DATA__ in Spotify embed page.\n"
            "The embed page structure may have changed — check _SPOTIFY_PATH in fetcher.py."
        )

    obj = json.loads(parser.json_text)
    track_list = _get_nested(obj, _SPOTIFY_PATH)
    if not isinstance(track_list, list):
        sys.exit(
            f"Spotify JSON path {_SPOTIFY_PATH} not found or not a list.\n"
            "Run the verification snippet in the README to discover the current structure."
        )

    yt = YTMusic()
    songs: list[dict] = []
    skipped: list[str] = []
    total = len(track_list)

    for i, item in enumerate(track_list, 1):
        print(f"\r  {i}/{total}", end="", flush=True)

        title = item.get("title", "")
        # subtitle is "Artist" or "Artist1,\xa0Artist2" — primary artist is before first comma
        subtitle = item.get("subtitle", "")
        artist = subtitle.split(",")[0].strip() if subtitle else "Unknown"

        if not title:
            skipped.append(f"track {i} (no title)")
            continue

        video_id, year = _search_year_and_id(yt, title, artist)
        time.sleep(0.15)

        if not video_id:
            skipped.append(f"{artist} – {title}")
            continue

        songs.append({
            "youtube_id": video_id,
            "title": title,
            "artist": artist,
            "year": year,
        })

    print()  # end progress line

    if skipped:
        print(f"  {len(skipped)} track(s) skipped (no YouTube match):")
        for s in skipped:
            print(f"    – {s}")

    _cache_save(cache_dir, cache_key, songs)
    return songs
