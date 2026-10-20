#!/usr/bin/env python3
"""WordNet 3.1（data/wordnet/dict）と機能語リストから、語ごとの品詞と語義数を data/pos_wikt.json に書く。
WordNetは名詞・動詞・形容詞・副詞しか持たないので、前置詞・接続詞・代名詞などは下のリストで補う。"""
import json, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
out = {}
for f, p in (("noun", "noun"), ("verb", "verb"), ("adj", "adj"), ("adv", "adv")):
    for line in open(os.path.join(D, "wordnet", "dict", "index." + f), encoding="utf-8"):
        if line.startswith(" "): continue
        a = line.split()
        if "_" in a[0]: continue
        out.setdefault(a[0], {})[p] = int(a[2])
FUNC = {
    "prep": "about above across after against along amid among around as at before behind below beneath beside besides between beyond but by concerning despite down during except for from in inside into like near of off on onto out outside over past per regarding round since than through throughout till to toward towards under underneath unlike until up upon via with within without",
    "conj": "after and although as because before but either for if lest neither nor once or since so than that though till unless until whereas whether while yet when where whenever wherever",
    "pron": "i me my mine myself you your yours yourself yourselves he him his himself she her hers herself it its itself we us our ours ourselves they them their theirs themselves this that these those who whom whose which what whatever whoever anybody anyone anything everybody everyone everything nobody none nothing somebody someone something one each either neither both all few many several some any much more most other another such",
    "det": "a an the this that these those my your his her its our their some any no every each either neither both all few many several much more most other another such what which whose enough",
    "intj": "oh ah hello hi wow alas ouch hey yes no okay ok goodbye bye please thanks",
}
for p, ws in FUNC.items():
    for w in ws.split():
        out.setdefault(w, {})[p] = 30
json.dump(out, open(os.path.join(D, "pos_wikt.json"), "w"), ensure_ascii=False)
print(len(out))
