#!/usr/bin/env python3
"""Wiktionary(kaikki.org経由)から語源を取得して data/etymology.json に保存。中断再開可。"""
import json, os, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "data", "etymology.json")
idx = json.load(open(os.path.join(ROOT, "..", "assets", "index.json")))
words = [r[0] for r in idx if r[0] == r[1] and len(r[0]) >= 2]
done = json.load(open(OUT)) if os.path.exists(OUT) else {}
todo = [w for w in words if w not in done]
print(len(words), "words,", len(todo), "todo", flush=True)

def get(w):
    url = f"https://kaikki.org/dictionary/English/meaning/{w[0]}/{w[:2]}/{w}.jsonl"
    for t in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "eigo-tango-build/1.0"}), timeout=30) as r:
                txt = r.read().decode("utf-8")
            for l in txt.splitlines():
                d = json.loads(l)
                if d.get("word") == w and d.get("etymology_text"):
                    return w, d["etymology_text"].strip()
            return w, ""
        except urllib.error.HTTPError as e:
            if e.code == 404: return w, ""
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return w, None

n = 0
with ThreadPoolExecutor(6) as ex:
    for w, e in ex.map(get, todo):
        if e is not None: done[w] = e
        n += 1
        if n % 500 == 0:
            json.dump(done, open(OUT, "w"), ensure_ascii=False); print(n, flush=True)
json.dump(done, open(OUT, "w"), ensure_ascii=False)
print("finished", len(done), "with etym:", sum(1 for v in done.values() if v), flush=True)
