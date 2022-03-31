from datetime import datetime
import libtmux
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.common.by import By
from subprocess import Popen
from time import sleep
import os

def now():
    return datetime.now().strftime("%d/%m/%y %H:%M:%S")

### INITIALIZE RECORDS ###
with open("/home/pi/fun/live/lrecord.txt", "a+") as f:
    pass
record = open("/home/pi/fun/live/lrecord.txt", "r+")
l = record.read()
if len(l) == 0:
    assigned = []
else:
    assigned = l.split("\n")
record.close()
record = open("/home/pi/fun/live/lrecord.txt", "a+")
log = open("/home/pi/fun/live/logs/main.log", "a+")


### INITIALIZE SELENIUM ###
options = webdriver.ChromeOptions()
options.add_argument("--headless"); # open Browser in maximized mode
options.add_argument("disable-infobars"); # disabling infobars
options.add_argument("--disable-extensions"); # disabling extensions
options.add_argument("--disable-gpu"); # applicable to windows os only
options.add_argument("--disable-dev-shm-usage"); # overcome limited resource problems
options.add_argument("--no-sandbox"); # Bypass OS security model

driver = webdriver.Chrome(options=options)
driver.get("https://holodex.net")
sleep(1)


### INITIALIZE LIBTMUX ###
server = libtmux.Server()
session = server.find_where({"session_name": "s"})
if not session:
    session = server.new_session("s", window_name="w")
window = session.list_windows()[0]
url_to_pane = {}


while True:

    ### RENDER WEBSITE ###
    try:
        print("start")
        urls = driver.find_elements(By.XPATH, "//a[@class='video-card no-decoration d-flex video-card-fluid flex-column']")

    except NoSuchElementException:
        sleep(1)
        print("sleep")
        continue


    ### GET CURRENT LIVE STREAMS ###
    live = []
    for url in urls:
        try:
            url.find_element(By.CLASS_NAME, "text-live")
            live.append(url.get_attribute("href"))
        except NoSuchElementException:
            pass
    urls = [x.split('/')[-1] for x in live if x is not None]
    print(urls)

    ### ASSIGN TMUX PANES ###
    for url in urls:
        print("process", url)
        in_dict = url in url_to_pane
        if in_dict:
            try:
                has_pane = window.get_by_id(url_to_pane[url]) is not None
            except Exception:
                has_pane = True
        else:
            has_pane = False

        #has_pane = in_dict and (window.get_by_id(url_to_pane[url]) is not None)

        if has_pane:
            continue
        
        if in_dict:
            # we had a pane for this, livestream is still up, but pane is dead
            print(f"{now()} {url} dropped, restarting")
            log.write(f"{now()} {url} dropped, restarting\n")

        else:
            log.write(f"{now()} {url} started\n")

        id = window.split_window(shell=f"python /home/pi/fun/live/lscrape.py {url} {url}").id
        window.select_layout('tiled')
        url_to_pane[url] = id

    print("end")

    record.flush()
    log.flush()

    driver.refresh()
    sleep(1)
    print("refresh")

record.close()
