from datetime import datetime
import libtmux
from time import sleep
import os

from modules.config import get_configs
from modules.indexer.holodex import HolodexIndexer
from modules.indexer.nijidex import NijisanjiIndexer
from modules.writer.database import DatabaseWriter
from modules.writer.filesystem import FilesystemWriter

def now():
    return datetime.now().strftime("%d/%m/%y %H:%M:%S")
    

def main():
    config_handler = get_configs()

    os.makedirs(os.path.join(config_handler.log_path), exist_ok=True)
    log = open(os.path.join(config_handler.log_path, "main.log"), "a+")

    ### INITIALIZE LIBTMUX ###
    server = libtmux.Server()
    session = server.sessions.get(session_name="holoscrape", default=None)
    if not session:
        session = server.new_session("holoscrape", window_name="main.py")
    window = session.windows[0]
    window.resize(width=220, height=50)
    url_to_pane = {}

    stream_indexers = (HolodexIndexer(config_handler), NijisanjiIndexer(config_handler))
    writers = []
    if config_handler.write_to_db:
        writers.append(DatabaseWriter(config_handler, None))
    if config_handler.write_to_local:
        for folder in ['simple', 'metadata']:
            os.makedirs(os.path.join(config_handler.local_path, folder), exist_ok=True)
        writers.append(FilesystemWriter(config_handler, None))

    while True:
        streams = []
        for indexer in stream_indexers:
            streams += indexer.get_streams()
        if not streams:
            sleep(60)
            continue

        for stream in streams:
           for w in writers:
                w.process_stream(stream)

        urls = [s['id'] for s in streams]

        to_del = []
        for u in url_to_pane.keys():
            if u not in urls:
                to_del.append(u)
                print(f"{now()} {u} finished")

        for u in to_del:
            del url_to_pane[u]

        ### ASSIGN TMUX PANES ###
        for url in urls:
            in_dict = url in url_to_pane
            if in_dict:
                has_pane = window.panes.get(pane_id=url_to_pane[url], default=None) is not None
            else:
                has_pane = False

            if has_pane:
                continue
            
            if in_dict:
                # we had a pane for this, livestream is still up, but pane is dead
                print(f"{now()} {url} dropped, restarting")
                log.write(f"{now()} {url} dropped, restarting\n")

            else:
                print(f"{now()} {url} started")
                log.write(f"{now()} {url} started\n")

            try:
                pane_id = window.split(shell=f"python3 {os.path.dirname(os.path.realpath(__file__))}/scrape.py {url} {url}").pane_id
            except libtmux.exc.LibTmuxException as e:
                print(f"{now()} {url} failed to split pane: {e}")
                log.write(f"{now()} {url} failed to split pane: {str(e)}\n")
                continue
            window.select_layout('tiled')
            url_to_pane[url] = pane_id

        sleep(60)

if __name__ == '__main__':
    main()
