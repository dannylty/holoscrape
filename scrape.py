from datetime import datetime
import os
import pytchat
import time
import sys
from random import randint

def now():
    return datetime.now().strftime("%d/%m/%y %H:%M:%S")

base_path = os.path.dirname(os.path.realpath(__file__))

retries = 0
while retries < 5:
    try:
        chat = pytchat.create(video_id=sys.argv[1])
        break
    except pytchat.exceptions.InvalidVideoIdException:
        retries += 1
        continue

path = f"{base_path}/data/full/{sys.argv[2]}_full.txt"
path_s = f"{base_path}/data/simple/{sys.argv[2]}_short.txt"

f = open(path, 'a+')
f_s = open(path_s, 'a+')
log = open(f"{base_path}/logs/scrape.log", "a+")
total_items = 0

log.write(f"{now()} {sys.argv[2]} started live scrape\n")
log.flush()
os.fsync(log)


while True:

    if chat.is_replay(): 
        log.write(f"{now()} {sys.argv[2]} replay detected\n")
        log.flush()
        break

    while chat.is_alive():

        for c in chat.get().sync_items():
            print(f"{sys.argv[2]} {c.datetime} {c.message}")
            f.write(c.json())
            f.write("\n")
            f_s.write(f"{c.datetime} {c.message}\n")
            total_items += 1
        f.flush()
        f_s.flush()

    try:
        chat.raise_for_status()

    except pytchat.ChatDataFinished:
        log.write(f"{now()} {sys.argv[2]} live finished with {total_items} items\n")
        log.flush()
        os.fsync(log)
        break
        
    except Exception as e:
        if retries < 5:
            time.sleep(2)
            chat = pytchat.create(video_id=sys.argv[1])
            retries += 1
            log.write(f"{now()} {sys.argv[2]} live {type(e)} {str(e)} retrying...\n")
            log.flush()
            continue

        log.write(f"{now()} {sys.argv[2]} live {type(e)} {str(e)}\n")
        log.flush()
        os.fsync(log)
        break

f.close()
f_s.close()
log.close()
