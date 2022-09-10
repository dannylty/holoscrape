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
        chat = pytchat.create(video_id=sys.argv[1])
        break
    except pytchat.exceptions.InvalidVideoIdException:
        retries += 1
        if retries > 5:
            quit()
        continue
    except Exception as e:
        print(str(e))
        quit()

path_s = f"{base_path}data/simple/{sys.argv[2]}_short.txt"

f_s = open(path_s, 'a+')
log = open(f"{base_path}/logs/scrape.log", "a+")
total_items = 0
total = 0

lock = threading.Lock()

log.write(f"{now()} {sys.argv[2]} started live scrape\n")

def post(cursor, chats, lock):
    lock.acquire()
    try:
        cursor.executemany('INSERT OR IGNORE INTO chat_tab(video_id, chat_id, text, timestamp, author_name, author_id) VALUES(?, ?, ?, ?, ?, ?)',
            seq_of_parameters=chats)
    except sqlite3.Error as e:
        print(str(e))
    except Exception as e:
        print(chats)
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
                #print(f"{total_items} {sys.argv[2]} {c.datetime} {c.message}")
                print(".", end="", flush=True)
                f_s.write(f"{total_items} {c.datetime} {c.message}\n")
                chats.append((sys.argv[2], c.id.replace('%3D', '='), c.message, c.timestamp, c.author.name, c.author.channelId))

                total_items += 1
            if len(chats) >= 100:
                print("\ncreating new thread")
                lock.acquire()
                t = threading.Thread(target=post, args=(cursor, tuple(chats), lock))
                t.start()
                threads.append(t)
                lock.release()
                if len(threads) > 3:
                    print("joining first thread")
                    s_time = time.time()
                    threads[0].join()
                    print("joining took", time.time() - s_time)
                    threads = threads[1:]

                uniq = len(set([c[1] for c in chats]))
                total += uniq
                print(sys.argv[2], 'raw:', len(chats), 'unique:', uniq, 'total_uniq:', total)
                chats = []

            else:
                time.sleep(1)

        try:
            chat.raise_for_status()

        except pytchat.ChatDataFinished :
            log.write(f"{now()} {sys.argv[2]} live finished with {total} items\n")
            break
            
        except Exception as e:
            if retries < 5:
                chat = pytchat.create(video_id=sys.argv[1])
                retries += 1
                log.write(f"{now()} {sys.argv[2]} live {type(e)} {str(e)} retrying...\n")
                continue

            log.write(f"{now()} {sys.argv[2]} live {type(e)} {str(e)} finished with {total} items\n")
            break
    
    if len(chats) > 0:
        post(cursor, tuple(chats), lock)

for t in threads:
    t.join()

conn.close()
f.close()
f_s.close()
log.close()
