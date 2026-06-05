# Setlist to Spotify Playlist

Creates a Spotify playlist from recent concert setlists. Give it a list of band names; it looks up their recent shows on setlist.fm, collects the songs they played, and adds them all to a new playlist in your Spotify account.

## Requirements

- Python 3.12+
- A [setlist.fm](https://www.setlist.fm) account and API key
- A [Spotify](https://www.spotify.com) account and developer app

---

## Setup

### 1. Get a setlist.fm API key

1. Create a free account at [setlist.fm](https://www.setlist.fm).
2. Go to [setlist.fm/settings/api](https://www.setlist.fm/settings/api) and apply for an API key. Fill in a brief description of your project (personal/non-commercial use is fine).
3. The key is issued immediately after approval (usually within minutes to a day).
4. Copy the key — you'll add it to `.env` in step 4.

> **Note:** The free tier allows personal, non-commercial use only. Usage is limited to 2 requests/second and a hard daily quota (resets at midnight UTC). For large festival lineups this quota can be exhausted in a single run — see [API response caching](#api-response-caching) below.

### 2. Get Spotify credentials

1. Log in to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Click **Create app**.
   - App name and description: anything you like (e.g. "My Setlist Tool").
   - Redirect URI: `http://127.0.0.1:8888/callback` — add this exactly. (Spotify blocks `localhost` by name; the loopback IP `127.0.0.1` is the correct alternative.)
   - APIs used: check **Web API**.
3. Click **Save**, then open your new app and go to **Settings**.
4. Copy the **Client ID** and **Client Secret**.

> **Note (as of 2025):** Spotify may require your app to be registered under a legally registered organization for some account types. If you hit this restriction, the app still works perfectly in *development mode* for up to 25 users — more than enough for personal use or sharing with friends.

> **Premium vs Free:** A Spotify Premium subscription is **not** required to create and manage playlists via the API. Free accounts work fine.

### 3. Install dependencies

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 4. Configure credentials

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```
SETLISTFM_API_KEY=your_setlistfm_api_key_here
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

> `.env` is listed in `.gitignore` and will not be committed.

---

## Usage

### Basic — band names as arguments

```bash
python main.py Radiohead
python main.py Radiohead "Arcade Fire" "Bon Iver"
```

### From a file

Create a plain text file with one band per line. Lines starting with `#` are treated as comments.

```
# bands.txt
Radiohead
Arcade Fire
# Bon Iver  ← skipped
```

```bash
python main.py --file bands.txt
```

You can combine both:

```bash
python main.py Radiohead --file more_bands.txt
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--name NAME` / `-n NAME` | Band names joined by ` + ` | Playlist name |
| `--shows N` / `-s N` | `5` | Number of recent shows to pull songs from |
| `--before DATE` | Today | Only include shows strictly before this date (`YYYY-MM-DD`) |
| `--public` | off (private) | Make the playlist public |
| `--file PATH` / `-f PATH` | — | Text file with one band per line |

### Filtering by date

By default, only shows that have already happened are included — upcoming shows listed on setlist.fm with an empty setlist are automatically ignored.

Use `--before` to pin the cutoff to a specific date in the past. This is useful for festival playlists (where you want the setlists right before the festival date) and for reproducible runs — re-running with the same `--before` date always produces the same result regardless of when you run it.

```bash
# Only shows before Graspop 2026 starts
python main.py --file graspop2026.txt --name "Graspop 2026" --before 2026-06-19

# Reproducible run — same output no matter when you re-run it
python main.py Radiohead --before 2025-01-01
```

### Examples

```bash
# Last 3 shows, custom playlist name
python main.py Radiohead --shows 3 --name "Radiohead Setlist"

# Multiple bands from a file, public playlist
python main.py --file bands.txt --name "Summer 2025" --public

# Mix of args and file
python main.py Radiohead --file more_bands.txt --shows 10
```

### First run — Spotify authorization

The first time you run the tool, `spotipy` will open a browser tab asking you to log in to Spotify and authorize the app. After you click **Agree**, Spotify redirects to `http://localhost:8888/callback`. Copy that full URL from your browser's address bar and paste it back into the terminal when prompted.

`spotipy` saves a token to `.cache` so subsequent runs happen silently.

---

## API response caching

All setlist.fm responses are cached to `.cache_setlistfm/` (one JSON file per request). On re-runs, cached responses are returned instantly without touching the API.

**Practical effect:** a 40-band festival lineup costs ~80 API calls on the first run, and **0** on every subsequent run.

**What goes stale and when:**

| Cached data | Staleness |
|---|---|
| Artist MBID lookups | Essentially permanent — band IDs never change |
| Setlist pages | Stale if the band played a new show since you last ran |

To refresh setlists for a specific band, delete their files from `.cache_setlistfm/`. To force a full re-fetch, delete the entire folder:

```bash
rm -rf .cache_setlistfm/
```

`.cache_setlistfm/` is listed in `.gitignore` and will not be committed.

---

## Adding new song selection strategies

Song selection lives entirely in [`song_selector.py`](song_selector.py). The API layer always returns raw setlist data, so no API changes are needed for new strategies.

To add a new strategy:

1. Write a function `select_<your_strategy>(setlists: list[dict], ...) -> list[str]`.
2. Register it in the `select_songs()` dispatcher with a new `elif strategy == "your_strategy":` branch.
3. Wire up the corresponding CLI flag in `main.py`.

Ideas for future strategies (all doable client-side):
- **Most-played** — songs sorted by frequency across N shows
- **Staples** — songs played in ≥ X% of fetched setlists
- **Recent window** — unique songs from shows within the last X months
