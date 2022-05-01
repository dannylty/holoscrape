import json
import os
from multiprocessing import Pool

def merge(s):
    root = "Z:\\live"
    machines = ['pi1', 'pi2', 'pi3']

    instances = list()

    for i in range(3):
        path = os.path.join(root, machines[i], "full", s)
        if os.path.exists(path):
            with open(path, 'r') as f:
                instances.append([json.loads(x) for x in f.read().split('\n')[:-1]])

    # I CAN DO THIS IN O(N) WITH A MERGE BUT IM TOO LAZY OKAY
    final = dict()
    for i in instances:
        for stream in i:
            final[stream['id']] = stream
    final = list(final.values())
    final.sort(key=lambda x: x['timestamp'])

    with open(os.path.join(root, "merged", "full", s[:-4] + ".json"), 'w+', encoding='utf8') as f:
        json.dump(final, f, ensure_ascii=False)

def main():
    root = "Z:\\live"
    machines = ['pi1', 'pi2', 'pi3']
    streams = set()
    for i in range(3):
        d = os.listdir(os.path.join(root, machines[i], "full"))
        for s in d:
            streams.add(s)

    streams = list(streams)
    print(len(streams))
    with Pool(24) as p:
        p.map(merge, streams)

if __name__ == "__main__":
    main()
