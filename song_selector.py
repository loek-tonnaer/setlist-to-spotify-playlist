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

def select_last_n_shows(setlists: list[dict], n: int, min_pct: float = 0) -> list[str]:
    """
    Unique songs from the N most recent setlists that were played in at least
    min_pct% of those shows, returned in first-seen order.
    min_pct=0 (default) includes every song that appeared at least once.
    """
    batch = setlists[:n]
    if not batch:
        return []
    counts: dict[str, int] = {}
    first_seen_order: dict[str, int] = {}
    order = 0
    for setlist in batch:
        for song in set(_live_songs(setlist)):
            counts[song] = counts.get(song, 0) + 1
            if song not in first_seen_order:
                first_seen_order[song] = order
                order += 1
    threshold = min_pct / 100 * len(batch)
    return [
        song for song in sorted(first_seen_order, key=first_seen_order.__getitem__)
        if counts[song] >= threshold
    ]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def select_songs(setlists: list[dict], strategy: str = "last_n", **kwargs) -> list[str]:
    """
    Apply a named selection strategy to a list of raw setlist dicts.

    Supported strategies
    --------------------
    last_n  All unique songs from the N most recent shows that appear in at
            least min_pct% of those shows.
            kwargs: n (int, default 5), min_pct (float, default 0)
    """
    if strategy == "last_n":
        return select_last_n_shows(setlists, n=kwargs.get("n", 5), min_pct=kwargs.get("min_pct", 0))
    raise ValueError(f"Unknown strategy: {strategy!r}")
