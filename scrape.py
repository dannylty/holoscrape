from datetime import datetime
import os
import pytchat
import pyrqlite.dbapi2 as db
import time
from socket import gethostname
import sqlite3
import sys
from random import randint
import threading

def now():
    return datetime.now().strftime("%d/%m/%y %H:%M:%S")

base_path = "/mnt/thumb/hololive/"

retries = 0
while True:
    try:
        chat = pytchat.LiveChat(video_id=sys.argv[1], buffer=pytchat.core_multithread.buffer.Buffer(maxsize=200))
        break
    except pytchat.exceptions.InvalidVideoIdException:
        retries += 1
        if retries > 5:
            quit()
        continue
    except Exception as e:
        print(str(e))
        quit()

path = f"{base_path}data/full/{sys.argv[2]}_full.txt"
path_s = f"{base_path}data/simple/{sys.argv[2]}_short.txt"

f = open(path, 'a+')
f_s = open(path_s, 'a+')
log = open(f"{base_path}/logs/scrape.log", "a+")
total_items = 0

lock = threading.Lock()

log.write(f"{now()} {sys.argv[2]} started live scrape\n")

def post(cursor, chats, lock):
    print(len(set([c[1] for c in chats])))
    lock.acquire()
    print(chats[0][1], "first", len(chats))
    try:
        cursor.executemany('INSERT OR IGNORE INTO chat_tab(video_id, chat_id, text, timestamp, author_name, author_id) VALUES(?, ?, ?, ?, ?, ?)',
            seq_of_parameters=chats)
    except sqlite3.Error as e:
        print(str(e))
    lock.release()

threads = []
chats = []

conn = db.connect(host=gethostname(), port=4001)
with conn.cursor() as cursor:
    while True:

        if chat.is_replay(): 
            log.write(f"{now()} {sys.argv[2]} replay detected\n")
            break

        while chat.is_alive():
            for c in chat.get().items:
                print(f"{total_items} {sys.argv[2]} {c.datetime} {c.message}")

                f_s.write(f"{total_items} {c.datetime} {c.message}\n")
                chats.append((sys.argv[2], c.id.replace('%3D', '='), c.message, c.timestamp, c.author.name, c.author.channelId))

                total_items += 1
            if len(chats) >= 100:
                print("creating new thread")
                print(len(chats))
                t = threading.Thread(target=post, args=(cursor, tuple(chats), lock))
                t.start()
                threads.append(t)
                if len(threads) > 3:
                    print("joining first thread")
                    s_time = time.time()
                    threads[0].join()
                    print("joining took", time.time() - s_time)
                    threads = threads[1:]

                chats = []

            else:
                time.sleep(1)

        try:
            chat.raise_for_status()

        except pytchat.ChatDataFinished:
            log.write(f"{now()} {sys.argv[2]} live finished with {total_items} items\n")
            break
            
        except Exception as e:
            if retries < 5:
                chat = pytchat.create(video_id=sys.argv[1])
                retries += 1
                log.write(f"{now()} {sys.argv[2]} live {type(e)} {str(e)} retrying...\n")
                continue

            log.write(f"{now()} {sys.argv[2]} live {type(e)} {str(e)}\n")
            break
    
    if len(chats) > 0:
        post(cursor, tuple(chats), lock)


conn.close()
f.close()
f_s.close()
log.close()
