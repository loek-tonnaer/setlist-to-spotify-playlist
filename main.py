import argparse
import datetime
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from setlist_client import SetlistClient
from song_selector import select_songs
from spotify_client import SpotifyClient

_MAX_NAME_LEN = 100  # Spotify playlist name character limit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a Spotify playlist from recent concert setlists.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s Radiohead\n"
            "  %(prog)s Radiohead 'Arcade Fire' --shows 3\n"
            "  %(prog)s --file bands.txt --name 'Summer Tour 2025'\n"
            "  %(prog)s Radiohead --file more_bands.txt --public"
        ),
    )
    parser.add_argument(
        "bands",
        nargs="*",
        metavar="BAND",
        help="One or more band names.",
    )
    parser.add_argument(
        "--file", "-f",
        metavar="PATH",
        help="Text file with one band name per line (# lines are ignored).",
    )
    parser.add_argument(
        "--name", "-n",
        default="",
        metavar="NAME",
        help="Playlist name. Defaults to a concatenation of all band names.",
    )
    parser.add_argument(
        "--shows", "-s",
        type=int,
        default=5,
        metavar="N",
        help="Number of recent shows to pull songs from (default: 5).",
    )
    parser.add_argument(
        "--before",
        metavar="DATE",
        default=None,
        help="Only include shows before this date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--staples",
        type=int,
        default=0,
        metavar="PCT",
        help=(
            "Only include songs played in at least PCT%% of the fetched shows "
            "(0–100, default: 0 = include every song played at least once)."
        ),
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Make the playlist public (default: private).",
    )
    return parser


def load_bands_from_file(path: str) -> list[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def default_playlist_name(bands: list[str]) -> str:
    name = " + ".join(bands)
    if len(name) > _MAX_NAME_LEN:
        name = name[: _MAX_NAME_LEN - 1] + "…"
    return name


def require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        print(f"Error: {key} is not set. See README.md for setup instructions.", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()

    bands: list[str] = list(args.bands)
    if args.file:
        bands += load_bands_from_file(args.file)

    if not bands:
        print("Error: provide at least one band via arguments or --file.", file=sys.stderr)
        sys.exit(1)

    if not (0 <= args.staples <= 100):
        print("Error: --staples must be between 0 and 100.", file=sys.stderr)
        sys.exit(1)

    if args.before:
        try:
            before_date = datetime.date.fromisoformat(args.before)
        except ValueError:
            print("Error: --before must be a date in YYYY-MM-DD format.", file=sys.stderr)
            sys.exit(1)
    else:
        before_date = datetime.date.today()

    playlist_name = args.name.strip() or default_playlist_name(bands)

    setlist_client = SetlistClient(require_env("SETLISTFM_API_KEY"))
    spotify_client = SpotifyClient(
        client_id=require_env("SPOTIFY_CLIENT_ID"),
        client_secret=require_env("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
    )

    all_track_uris: list[str] = []

    for band in bands:
        print(f"\n[{band}]")
        try:
            mbid = setlist_client.get_artist_mbid(band)
        except ValueError as exc:
            print(f"  Warning: {exc} — skipping.")
            continue

        print(f"  Artist ID: {mbid}")
        print(f"  Fetching last {args.shows} setlist(s)...")
        setlists = setlist_client.get_setlists(mbid, args.shows, before=before_date)
        print(f"  Got {len(setlists)} setlist(s).")

        songs = select_songs(setlists, strategy="last_n", n=args.shows, min_pct=args.staples)
        print(f"  {len(songs)} unique song(s) across those shows.")

        print("  Searching Spotify...")
        found = 0
        for song in songs:
            uri = spotify_client.find_track_uri(song, band)
            if uri:
                all_track_uris.append(uri)
                found += 1
            elif "/" in song:
                parts = [p.strip() for p in song.split("/") if p.strip()]
                part_uris = []
                for part in parts:
                    part_uri = spotify_client.find_track_uri(part, band)
                    if part_uri:
                        part_uris.append(part_uri)
                    else:
                        print(f"    Not found on Spotify: {part!r} (from medley {song!r})")
                all_track_uris.extend(part_uris)
                found += len(part_uris)
            else:
                print(f"    Not found on Spotify: {song!r}")
        print(f"  {found}/{len(songs)} track(s) matched.")

    if not all_track_uris:
        print("\nNo tracks found — playlist not created.", file=sys.stderr)
        sys.exit(1)

    print(f"\nCreating playlist {playlist_name!r} with {len(all_track_uris)} track(s)...")
    url = spotify_client.create_playlist(playlist_name, all_track_uris, public=args.public)
    print(f"Done! {url}")


if __name__ == "__main__":
    main()
