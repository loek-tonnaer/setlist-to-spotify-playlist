"""
Song selection strategies.

Each strategy receives the full list of raw setlist dicts returned by
SetlistClient.get_setlists() and returns a deduplicated list of song names.
Adding a new strategy means writing one function and registering it in
select_songs() — no changes to the API layer are needed.
"""


def _live_songs(setlist: dict) -> list[str]:
    """Extract performed (non-tape) song names from a single setlist dict."""
    songs = []
    for section in setlist.get("sets", {}).get("set", []):
        for song in section.get("song", []):
            if song.get("tape", False):
                continue
            name = song.get("name", "").strip()
            if name:
                songs.append(name)
    return songs


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def select_last_n_shows(setlists: list[dict], n: int) -> list[str]:
    """All unique songs played across the N most recent setlists, in first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for setlist in setlists[:n]:
        for song in _live_songs(setlist):
            if song not in seen:
                seen.add(song)
                result.append(song)
    return result


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def select_songs(setlists: list[dict], strategy: str = "last_n", **kwargs) -> list[str]:
    """
    Apply a named selection strategy to a list of raw setlist dicts.

    Supported strategies
    --------------------
    last_n  All unique songs from the N most recent shows.
            kwargs: n (int, default 5)
    """
    if strategy == "last_n":
        return select_last_n_shows(setlists, n=kwargs.get("n", 5))
    raise ValueError(f"Unknown strategy: {strategy!r}")
