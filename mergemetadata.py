import json
import os
from multiprocessing import Pool

def merge(s):
    root = "Z:\\live"
    machines = ['pi1', 'pi2', 'pi3']

    items = []

    for i in range(3):
        path = os.path.join(root, machines[i], "metadata", s)
        if os.path.exists(path):
            with open(path, 'r') as f:
                curr = json.loads(f.read())
                del curr['live_viewers']
                items.append(curr)

    assert all(x == items[0] for x in items), "\n".join([str(i) for i in items])
        
    with open(os.path.join(root, "merged", "metadata", s[:-4] + ".json"), 'w+', encoding='utf8') as f:
        json.dump(items[0], f, ensure_ascii=False)

def main():
    root = "Z:\\live"
    machines = ['pi1', 'pi2', 'pi3']
    streams = set()
    for i in range(3):
        d = os.listdir(os.path.join(root, machines[i], "metadata"))
        for s in d:
            streams.add(s)

    streams = list(streams)
    print(len(streams))
    with Pool(24) as p:
        p.map(merge, streams)

if __name__ == "__main__":
    main()
