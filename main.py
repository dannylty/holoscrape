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
    session = server.find_where({"session_name": "holoscrape"})
    if not session:
        session = server.new_session("holoscrape", window_name="main.py")
    window = session.list_windows()[0]
    url_to_pane = {}

    stream_indexers = (HolodexIndexer(), NijisanjiIndexer())
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
                try:
                    has_pane = window.get_by_id(url_to_pane[url]) is not None
                except:
                    has_pane = True
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

            id = window.split_window(shell=f"python3 {os.path.dirname(os.path.realpath(__file__))}/scrape.py {url} {url}").id
            session.list_windows()[0].select_layout('tiled')
            url_to_pane[url] = id

        sleep(60)

if __name__ == '__main__':
    main()
