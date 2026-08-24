<p align="center"><img src="https://user-images.githubusercontent.com/63136392/201978731-094594a5-13c5-4407-8a0f-6c0dc50bed99.png"/></p>

<p align="center">Automated Extensible YouTube Livestream Chat Scraper and Visualiser.</p>

<p align="center"><kbd><img src="https://user-images.githubusercontent.com/63136392/201944147-5576e35c-a241-471c-b0bd-1110b08a3cca.png" width="828" height="507"/></kbd></p>

[![Tests](https://github.com/dannylty/holoscrape/actions/workflows/tests.yaml/badge.svg)](https://github.com/dannylty/holoscrape/actions/workflows/tests.yaml)
[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

## Main Features
* **Automatically detect existing livestreams.** Polls configured indexers (Holodex API) on an interval.
* **Dispatch to tmux panes or subprocesses in real time.** Each live stream gets its own scraper process.
* **Customisable writers.** Write to MySQL, write to local files, or create your own.
* **Configurable indexers.** Specify which organisations and channel filters to track.
* **Graceful shutdown.** SIGTERM/SIGINT handled cleanly; buffers are flushed before exit.
* **Log rotation.** Per-stream log files with size-based rotation.

## How To

### Installing Requirements
```
sudo apt install tmux   # only needed for tmux mode
pip3 install -r requirements.txt
```

### Configuring

The in-built Holodex indexer requires an API key via the env var `HOLODEX_API_KEY`.

Config reading defaults to `config.json` (override with `HOLOSCRAPE_CONFIG` env var).

```json
{
    "write_to_db": true,
    "db_host": "192.168.1.100",
    "db_port": 3306,
    "db_user": "holoscrape",
    "db_password": "password",
    "db_database": "holoscrape",
    "db_table": "chat_tab",
    "db_stream_table": "stream_tab",
    "db_nshards": 30,

    "write_to_local": true,
    "local_path": "/var/log/hololive/data/",

    "log_path": "/var/log/hololive/logs/",
    "log_level": "INFO",
    "log_format": "text",

    "poll_interval": 60,
    "max_concurrent_streams": 10,

    "indexers": [
        {"type": "holodex", "org": "Hololive"},
        {"type": "holodex", "org": "Nijisanji", "filter": "EN"}
    ]
}
```

All fields except `log_path` are optional. If `indexers` is omitted, it defaults
to Hololive + Nijisanji EN.

If `write_to_db` is `false`, all `db_*` fields can be omitted.
If `write_to_local` is `false`, `local_path` can be omitted.

The DB password can be set via `HOLOSCRAPE_DB_PASSWORD` env var to avoid
storing it in the config file.

A database schema generator is provided:
```
python resources/generate_init_sql.py --nshards 30 --table chat_tab -o init.sql
```

### Running

**tmux mode (default):**
```
python3 main.py
# ctrl-b s to switch to the scraping window
```

**subprocess mode (for systemd, docker, etc.):**
```
python3 main.py --no-tmux
```

**standalone scraper (single video):**
```
python3 scrape.py <video_id> [max_messages] [max_duration_seconds]
```

### Environment Variables

| Variable | Purpose |
|---|---|
| `HOLODEX_API_KEY` | API key for the Holodex indexer |
| `HOLOSCRAPE_CONFIG` | Path to config file (overrides CWD/project root search) |
| `HOLOSCRAPE_DB_PASSWORD` | DB password (overrides config file value) |

## Architecture

```
main.py          — poll loop, stream detection, process management
scrape.py        — single-video scraper (pytchat → writers)
modules/
  config.py      — config loading + validation
  utils.py       — shared helpers
  indexer/       — stream discovery (Holodex API)
  writer/        — output (MySQL, filesystem)
  logger/        — rotating file logger
```

The main process polls indexers every `poll_interval` seconds. When a new
live stream is detected, it spawns a `scrape.py` subprocess (or tmux pane).
When the stream disappears from the indexer results, the scraper is
allowed to finish naturally.
