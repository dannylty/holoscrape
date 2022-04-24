from datetime import datetime, timedelta
import json
import os
import socket
import subprocess

for stream in os.listdir("data/metadata"):
    if stream == '.gitignore':
        continue
    
    curr_path = os.path.join("data/metadata", stream)
    with open(curr_path, 'r') as f:
        text = f.read()
    time = json.loads(text)['published_at']
    dt = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.000Z")
    if datetime.now() - timedelta(days=2) > dt:
        share_path = f"/mnt/share/live/{socket.gethostname()}"
        
        key = {"full":"_full", "simple":"_short", "metadata":""}
        for folder in ["full", "simple", "metadata"]:
            subprocess.run(["mv", os.path.join("data", folder, stream[:-4] + key[folder] + '.txt'), os.path.join(share_path, folder, stream)])


