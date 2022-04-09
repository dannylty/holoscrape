from datetime import datetime
import libtmux
import requests
import json
import socket
from subprocess import Popen
from time import sleep
import os

def now():
    return datetime.now().strftime("%d/%m/%y %H:%M:%S")

log = open(f"{os.path.dirname(os.path.realpath(__file__))}/logs/main.log", "a+")


### INITIALIZE LIBTMUX ###
server = libtmux.Server()
session = server.find_where({"session_name": "s"})
if not session:
    session = server.new_session("s", window_name="w")
window = session.list_windows()[0]
url_to_pane = {}


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
        
        path = f"{os.path.dirname(os.path.realpath(__file__))}/data/metadata/{stream['id']}.txt"
        if not os.path.exists(path):
            with open(path, 'w+') as f:
                json.dump(stream, f, indent=4, ensure_ascii=False)

        urls.append(stream['id'])

    print(urls)


    ### ASSIGN TMUX PANES ###
    for url in urls:
        print("process", url)
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
            log.write(f"{now()} {url} started\n")

        id = window.split_window(shell=f"python {os.path.dirname(os.path.realpath(__file__))}/scrape.py {url} {url}").id
        window.select_layout('tiled')
        url_to_pane[url] = id

    print("end")

    log.flush()
