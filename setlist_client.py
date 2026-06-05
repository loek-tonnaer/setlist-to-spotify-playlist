from __future__ import annotations

import datetime
import json
import time
import urllib.parse
from pathlib import Path

import requests

SETLISTFM_BASE = "https://api.setlist.fm/rest/1.0"
_RATE_DELAY = 0.7  # stay comfortably under the 2 req/sec free-tier limit
_CACHE_DIR = Path(__file__).parent / ".cache_setlistfm"


class SetlistClient:
    def __init__(self, api_key: str):
        self._session = requests.Session()
        self._session.headers.update({
            "x-api-key": api_key,
            "Accept": "application/json",
        })
        self._last_request = 0.0
        _CACHE_DIR.mkdir(exist_ok=True)

    def _cache_path(self, path: str, params: dict | None) -> Path:
        key = path + ("?" + urllib.parse.urlencode(sorted((params or {}).items())))
        safe = key.replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "-")
        return _CACHE_DIR / f"{safe}.json"

    def _get(self, path: str, params: dict | None = None) -> dict:
        cache_file = self._cache_path(path, params)
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))

        for attempt in range(5):
            elapsed = time.monotonic() - self._last_request
            if elapsed < _RATE_DELAY:
                time.sleep(_RATE_DELAY - elapsed)
            response = self._session.get(f"{SETLISTFM_BASE}{path}", params=params)
            self._last_request = time.monotonic()
            if response.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()
            cache_file.write_text(json.dumps(data), encoding="utf-8")
            return data
        response.raise_for_status()
        return response.json()

    def get_artist_mbid(self, name: str) -> str:
        """Return the MusicBrainz ID for the best-matching artist name."""
        data = self._get("/search/artists", {"artistName": name, "sort": "relevance"})
        artists = data.get("artist", [])
        if not artists:
            raise ValueError(f"No artist found for: {name!r}")
        return artists[0]["mbid"]

    def get_setlists(self, mbid: str, count: int, before: datetime.date | None = None) -> list[dict]:
        """
        Return up to `count` most-recent setlists for the given artist with a date
        strictly before `before` (defaults to today, filtering out future/empty shows).

        Paginates automatically and stops as soon as `count` setlists are collected
        or all pages are exhausted. Callers receive raw API dicts so that any
        selection strategy can be applied client-side without extra API calls.
        """
        if before is None:
            before = datetime.date.today()
        collected: list[dict] = []
        page = 1
        while len(collected) < count:
            data = self._get(f"/artist/{mbid}/setlists", {"p": page})
            batch = data.get("setlist", [])
            if not batch:
                break
            for setlist in batch:
                # eventDate format from the API is "DD-MM-YYYY"
                try:
                    event_date = datetime.datetime.strptime(setlist["eventDate"], "%d-%m-%Y").date()
                except (KeyError, ValueError):
                    continue
                if event_date < before:
                    collected.append(setlist)
                    if len(collected) == count:
                        break
            total = data.get("total", 0)
            per_page = data.get("itemsPerPage", 20)
            if page * per_page >= total:
                break
            page += 1
        return collected
