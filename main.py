from datetime import datetime
import libtmux
import requests
import json
import socket
from subprocess import Popen
from time import sleep
import os
import sqlite3
from socket import gethostname
import pyrqlite.dbapi2 as db

def now():
    return datetime.now().strftime("%d/%m/%y %H:%M:%S")

log = open(f"/mnt/thumb/hololive/logs/main.log", "a+")


### INITIALIZE LIBTMUX ###
server = libtmux.Server()
session = server.find_where({"session_name": "s"})
if not session:
    session = server.new_session("s", window_name="w")
window = session.list_windows()[0]
url_to_pane = {}

conn = db.connect(host=gethostname(), port=4001)
while True:

    ### GET CURRENT LIVE STREAMS ###
    try:
        streams = requests.get("https://holodex.net/api/v2/live?type=placeholder%2Cstream&org=Hololive").json()
    except:
        continue

    urls = []

    for stream in streams:
        if stream['type'] == 'placeholder' or stream['status'] != 'live':
            continue

        if 'topic_id' in stream and stream['topic_id'] == 'membersonly':
            continue
        
        path = f"/mnt/thumb/hololive/data/metadata/{stream['id']}.txt"
        if not os.path.exists(path):
            with open(path, 'w+') as f:
                json.dump(stream, f, indent=4, ensure_ascii=False)
        with conn.cursor() as cursor:
            try:
                cursor.execute('INSERT OR IGNORE INTO stream_tab(id, title, topic_id, start_actual, channel_id, channel_name) VALUES(?, ?, ?, ?, ?, ?)',
                    (stream['id'], stream['title'], stream.get('topic_id', None), stream.get('start_actual', None), stream['channel']['id'], stream['channel']['name']))
            except sqlite3.Error as e:
                pass
            except Exception as e:
                print(str(e))
                print(stream)
                exit(1)

        urls.append(stream['id'])

    for u in url_to_pane.keys():
        if u not in urls:
            del url_to_pane[u]
            print(u, "finished")

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
