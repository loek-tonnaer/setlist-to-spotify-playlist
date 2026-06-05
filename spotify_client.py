from __future__ import annotations

import spotipy
from spotipy.oauth2 import SpotifyOAuth

_SCOPES = "playlist-modify-public playlist-modify-private"
_BATCH_SIZE = 100  # Spotify API limit per add-tracks call


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self._sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=_SCOPES,
            )
        )

    def find_track_uri(self, song: str, artist: str) -> str | None:
        """Return the Spotify URI for the best-matching track, or None if not found."""
        query = f"track:{song} artist:{artist}"
        results = self._sp.search(q=query, type="track", limit=1)
        items = results.get("tracks", {}).get("items", [])
        return items[0]["uri"] if items else None

    def create_playlist(self, name: str, track_uris: list[str], public: bool = False) -> str:
        """Create a new playlist, populate it in batches, and return its Spotify URL."""
        playlist = self._sp._post("me/playlists", payload={"name": name, "public": public})
        playlist_id = playlist["id"]
        for i in range(0, len(track_uris), _BATCH_SIZE):
            self._sp.playlist_add_items(playlist_id, track_uris[i : i + _BATCH_SIZE])
        return playlist["external_urls"]["spotify"]
