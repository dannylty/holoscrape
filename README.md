<p align="center"><img src="https://user-images.githubusercontent.com/63136392/201956597-bfb282ab-9117-47b2-a687-226575b8d69f.png"/></p>
<p align="center">Automated YouTube stream chat scraper and visualiser.</p>

<p align="center"><kbd><img src="https://user-images.githubusercontent.com/63136392/201944147-5576e35c-a241-471c-b0bd-1110b08a3cca.png" width="828" height="507"/></kbd></p>

[![Project Status: Active – The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-390/) 


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
Config reading defaults to `default_config.json`.

If `write_to_db` or `write_to_local` is `false`, their respective subconfigs can be omitted.

```
{
    "write_to_db": true, <-- Mandatory
    "db_host": "192.168.1.62",
    "db_port": 3306,
    "db_user": "pi",
    "db_password": "holoscrape",
    "db_database": "holoscrape",
    "db_table": "chat_tab_v3",
    "db_stream_table": "stream_tab",
    "db_nshards": 30,

    "write_to_local": true, <-- Mandatory
    "local_path": "/mnt/thumb/hololive/data/",
    
    "log_path": "/mnt/thumb/hololive/logs/" <-- Mandatory
}
```
### Running (in tmux)
```
python3 main.py
```

### License
This software is published under the [GPLv3](https://www.gnu.org/licenses/gpl-3.0.en.html) license. 
