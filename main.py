from datetime import datetime
import libtmux
import requests
import json
import socket
from subprocess import Popen
from time import sleep
import os
from socket import gethostname
import mysql.connector as db

from modules.config import get_configs
from modules.indexer.holodex import HolodexIndexer
from modules.writer.database import DatabaseWriter
from modules.writer.filesystem import FilesystemWriter

def now():
    return datetime.now().strftime("%d/%m/%y %H:%M:%S")
    

def main():
    config_handler = get_configs()

    log = open(os.path.join(config_handler.local_path, "logs/main.log"), "a+")

    ### INITIALIZE LIBTMUX ###
    server = libtmux.Server()
    session = server.find_where({"session_name": "s"})
    if not session:
        session = server.new_session("s", window_name="w")
    window = session.list_windows()[0]
    url_to_pane = {}

    conn = db.connect(
        host=config_handler.db_host,
        user=config_handler.db_user,
        password=config_handler.db_password,
        database=config_handler.db_database
    )

    cursor = conn.cursor()

    stream_indexer = HolodexIndexer()
    writers = [DatabaseWriter(config_handler, None), FilesystemWriter(config_handler, None)]

    while True:

        streams = stream_indexer.get_streams()
        if not streams: continue

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

            id = window.split_window(shell=f"python {os.path.dirname(os.path.realpath(__file__))}/scrape.py {url} {url}").id
            window.select_layout('tiled')
            url_to_pane[url] = id

        log.flush()
    conn.close()

if __name__ == '__main__':
    main()