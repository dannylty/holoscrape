<p align="center"><img src="https://user-images.githubusercontent.com/63136392/201978731-094594a5-13c5-4407-8a0f-6c0dc50bed99.png"/></p>

<p align="center">Automated Extensible YouTube Livestream Chat Scraper and Visualiser.</p>

<p align="center"><kbd><img src="https://user-images.githubusercontent.com/63136392/201944147-5576e35c-a241-471c-b0bd-1110b08a3cca.png" width="828" height="507"/></kbd></p>

[![Tests](https://github.com/dannylty/holoscrape/actions/workflows/tests.yaml/badge.svg)](https://github.com/dannylty/holoscrape/actions/workflows/tests.yaml)
[![Project Status: Active – The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/release/python-3144/) 


## Main Features
* <b>Automatically detect existing livestreams.</b> Polling will be done periodically to the specified indexers. The indexers are in charge of generating live YouTube video-ids to be scraped.
* <b>Dispatch to tmux panes in real time.</b> Display current streams in an interactive pane which will grow or shrink in size as live streams come and go.
* <b>Customisable processors</b>. Write to a database, write to files, or create your own processor.
* <b>Customisable indexers</b>. Don't follow Hololive? Write your own indexers instead to produce video-ids of your favourite streamers.

## How To
### Installing Requirements
```
sudo apt install tmux
pip3 install -r requirements.txt
```
### Configuring
The in-built Holodex indexers require API keys to be supplied, and they are given by
the env var `HOLODEX_API_KEY`.

Config reading defaults to `config.json`.

If `write_to_db` or `write_to_local` is `false`, their respective subconfigs can be omitted.

```
{
    "write_to_db": true, <-- Mandatory
    "db_host": <host>,
    "db_port": <port>,
    "db_user": "username",
    "db_password": "password",
    "db_database": "holoscrape",
    "db_table": "example_tab",
    "db_stream_table": "stream_tab",
    "db_nshards": 30,

    "write_to_local": true, <-- Mandatory
    "local_path": "/path/to/data/",

    "log_path": "/path/to/logs/", <-- Mandatory
}
```
An example database schema is given in `init.sql` that works with the example configs above. If you don't know your way around it, just turn `write_to_db` off.

### Running (in tmux)
```
python3 main.py
'ctrl-b s' to change to the scraping window
```
