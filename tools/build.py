#!/usr/bin/env python3
"""英和辞書サイトの静的ビルド。 python3 tools/build.py

データ:
  EJDict-hand (パブリックドメイン) … 語義
  Tatoeba (CC BY 2.0 FR)            … 例文と出現頻度
  CMUdict (BSD系)                   … 発音
環境変数 BASE_URL で sitemap / canonical の絶対URLを切り替える(独自ドメイン取得後)。
"""
import os, re, json, html, random, shutil
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tools", "data")
OUT = ROOT
BASE_URL = os.environ.get("BASE_URL", "https://kaitoinoue0921.github.io/eigo-tango").rstrip("/")
SITE = "サクッと英和"
MIN_COUNT = 8          # 例文コーパスでの最低出現回数（薄いページを作らない）
MAX_EX = 3

random.seed(7)
esc = html.escape

# ---------- 辞書 ----------
def load_ejdict():
    d = {}
    for line in open(os.path.join(DATA, "ejdict.txt"), encoding="utf-8"):
        line = line.rstrip("\n")
        if "\t" not in line:
            continue
        heads, mean = line.split("\t", 1)
        for h in [x.strip() for x in heads.split(",")]:
            h = h.lower()
            if re.fullmatch(r"[a-z]+", h):
                d.setdefault(h, []).append(mean)
    return d

KATA = re.compile(r"[ァ-ヶー]")
def split_bullets(s):
    out, cur, depth = [], "", 0
    for i, ch in enumerate(s):
        if ch in "〈《(（": depth += 1
        elif ch in "〉》)）": depth = max(0, depth - 1)
        if ch == "・" and depth == 0 and not (i > 0 and KATA.match(s[i-1]) and i+1 < len(s) and KATA.match(s[i+1])):
            if cur.strip(): out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip(): out.append(cur.strip())
    return out

def fmt_sense(t):
    t = re.sub(r"〈[CU]〉", "", t)
    t = t.replace("《", "<span class='n'>《").replace("》", "》</span>")
    t = re.sub(r"『([^』]*)』", r"<b>\1</b>", t)
    return t

def key_terms(means):
    terms = []
    for m in means:
        for t in re.findall(r"『([^』]+)』", m):
            t = t.strip()
            if t and t not in terms and re.search(r"[぀-ヿ一-鿿]", t) and not re.fullmatch(r"[名動形副]", t):
                terms.append(t)
    return terms

def plain_summary(means):
    terms = key_terms(means)
    if terms:
        return "、".join(terms[:5])
    m = re.sub(r"[《〈][^》〉]*[》〉]", "", means[0])
    m = re.sub(r"[『』]", "", m).split("/")[0]
    m = split_bullets(m)[0] if m.strip() else m
    return m.strip()[:40]


# ---------- カタカナ語 ----------
def load_kata():
    d = {}
    for line in open(os.path.join(ROOT, "tools", "katakana.tsv"), encoding="utf-8"):
        w, k = line.rstrip("\n").split("\t")
        d[w] = k.split(",")
    return d
KATA_WORDS = {}

# ---------- 発音 ----------
ARPA = {"AA":"ɑ","AE":"æ","AH":"ʌ","AO":"ɔ","AW":"aʊ","AY":"aɪ","EH":"ɛ","ER":"ɚ","EY":"eɪ","IH":"ɪ","IY":"i",
        "OW":"oʊ","OY":"ɔɪ","UH":"ʊ","UW":"u","B":"b","CH":"tʃ","D":"d","DH":"ð","F":"f","G":"ɡ","HH":"h",
        "JH":"dʒ","K":"k","L":"l","M":"m","N":"n","NG":"ŋ","P":"p","R":"r","S":"s","SH":"ʃ","T":"t",
        "TH":"θ","V":"v","W":"w","Y":"j","Z":"z","ZH":"ʒ"}
def load_cmu():
    d = {}
    for line in open(os.path.join(DATA, "cmudict.txt"), encoding="latin-1"):
        parts = line.split("#")[0].split()
        if len(parts) < 2: continue
        w = parts[0]
        if "(" in w: continue
        ph = []
        for p in parts[1:]:
            m = re.fullmatch(r"([A-Z]+)([012])?", p)
            if not m: break
            base, st = m.group(1), m.group(2)
            if base == "AH" and st == "0": ipa = "ə"
            elif base == "ER" and st == "0": ipa = "ɚ"
            else: ipa = ARPA[base]
            if st == "1": ph.append("ˈ")
            elif st == "2": ph.append("ˌ")
            ph.append(ipa)
        else:
            v = sum(1 for p in parts[1:] if p[:2] in ARPA and p[-1] in "012")
            if v <= 1: ph = [x for x in ph if x not in ("ˈ", "ˌ")]
            d[w] = "".join(ph)
    return d

# ---------- 屈折形 ----------
def forms(w):
    f = {w + "s", w + "ed", w + "ing"}
    if w.endswith("e"):
        f |= {w + "d", w[:-1] + "ing"}
    if w.endswith(("s", "x", "z", "ch", "sh")): f.add(w + "es")
    if w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
        f |= {w[:-1] + "ies", w[:-1] + "ied"}
    if re.search(r"[^aeiou][aeiou][bdgmnprt]$", w):
        f |= {w + w[-1] + "ed", w + w[-1] + "ing"}
    return f

# ---------- Tatoeba ----------
def load_tatoeba():
    eng = {}
    for line in open(os.path.join(DATA, "eng.tsv"), encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) == 3: eng[p[0]] = p[2]
    jpn = {}
    for line in open(os.path.join(DATA, "jpn.tsv"), encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) == 3: jpn[p[0]] = p[2]
    pairs = {}  # eng id -> jpn text
    for line in open(os.path.join(DATA, "links.tsv"), encoding="utf-8"):
        a, b = line.split()
        if a in jpn and b in eng and b not in pairs:
            pairs[b] = jpn[a]
    return eng, pairs

TOK = re.compile(r"[a-z]+(?:'[a-z]+)?")

def main():
    ej = load_ejdict()
    KATA_WORDS.update(load_kata())
    cmu = load_cmu()
    eng, pairs = load_tatoeba()
    print("dict", len(ej), "eng", len(eng), "pairs", len(pairs))

    cnt = Counter()
    for s in eng.values():
        cnt.update(set(TOK.findall(s.lower())))  # 文書頻度（1文に複数回出ても1）
    ranked = [w for w, c in cnt.most_common() if w in ej and c >= MIN_COUNT]
    rank = {w: i + 1 for i, w in enumerate(ranked)}
    print("pages", len(ranked))

    # 例文候補: 日本語訳つき・短め
    cand = defaultdict(list)
    need = set(ranked)
    for sid, jp in pairs.items():
        s = eng[sid]
        if not (25 <= len(s) <= 90) or len(jp) > 90 or "\t" in s: continue
        toks = set(TOK.findall(s.lower()))
        for t in toks & need:
            cand[t].append(sid)
        # 屈折形経由
    form_of = {}
    for w in ranked:
        if w.endswith(("ing", "ed")) or len(w) < 3:
            continue
        for f in forms(w):
            if f not in rank and f not in ej:
                form_of.setdefault(f, w)
    for sid in pairs:
        s = eng[sid]
        if not (25 <= len(s) <= 90): continue
        for t in set(TOK.findall(s.lower())):
            b = form_of.get(t)
            if b and len(cand[b]) < 400: cand[b].append(sid)

    words = {}
    for w in ranked:
        ids = list(dict.fromkeys(cand.get(w, [])))
        random.shuffle(ids)
        ids.sort(key=lambda i: abs(len(eng[i]) - 48))  # 中くらいの長さを優先
        pick = []
        for i in ids:
            if len(pick) >= MAX_EX: break
            pick.append(i)
        means = ej[w]
        words[w] = dict(w=w, rank=rank[w], means=means, ex=pick, ipa=cmu.get(w),
                        summary=plain_summary(means), terms=key_terms(means))

    if os.environ.get("EXPORT_DB"):
        export_db(os.environ["EXPORT_DB"], words, eng, pairs, form_of)
        return
    build_site(words, eng, pairs, form_of)

# ---------- アプリ用SQLite ----------
def export_db(path, words, eng, pairs, form_of):
    import sqlite3
    if os.path.exists(path): os.remove(path)
    db = sqlite3.connect(path)
    db.executescript("""
    create table words(word text primary key, rank integer, ipa text, summary text, terms text, senses text, etym text, kana text, etym_ja text);
    create table examples(word text, en text, ja text, tid integer);
    create index ex_w on examples(word);
    create table idx(term text, word text, kind integer);   -- kind 0=見出し 1=活用形 2=カタカナ
    create index idx_t on idx(term);
    """)
    kata = load_kata()
    etf = os.path.join(DATA, "etymology.json")
    et = json.load(open(etf, encoding="utf-8")) if os.path.exists(etf) else {}
    for w, x in words.items():
        blocks = []
        for m in x["means"]:
            blocks += [b.strip() for b in m.split(" / ") if b.strip()]
        senses = json.dumps([[re.sub(r"〈[CU]〉", "", q) for q in split_bullets(b)[:10]] for b in blocks[:14]], ensure_ascii=False)
        e = re.sub(r"\s+", " ", et.get(w, "")).strip()
        if len(e) > 700:
            cut = e[:700]; e = cut[:cut.rfind(". ") + 1] if ". " in cut[300:] else cut.rstrip() + "…"
        db.execute("insert into words values(?,?,?,?,?,?,?,?,?)",
                   (w, x["rank"], x["ipa"], x["summary"], "、".join(x["terms"][:6]), senses, e, "・".join(kata.get(w, [])),
                    json.dumps(load_etym_ja()[w], ensure_ascii=False) if w in load_etym_ja() else ""))
        for sid in x["ex"]:
            db.execute("insert into examples values(?,?,?,?)", (w, eng[sid], pairs[sid], int(sid)))
        db.execute("insert into idx values(?,?,0)", (w, w))
        for k in kata.get(w, []):
            db.execute("insert into idx values(?,?,2)", (k, w))
    for f, b in form_of.items():
        if b in words: db.execute("insert into idx values(?,?,1)", (f, b))
    db.commit(); db.execute("vacuum"); db.close()
    print("exported", path, os.path.getsize(path) // 1024, "KB")

# ---------- HTML ----------
def head(title, desc, path, extra=""):
    canon = f"{BASE_URL}/{path}".rstrip("/") if path else BASE_URL + "/"
    up = "../" * path.count("/")
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canon)}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>%F0%9F%93%97</text></svg>">
<link rel="stylesheet" href="{up}assets/style.css">
{extra}
</head>
<body data-up="{up}">
<header class="site-head"><div class="wrap">
  <a class="brand" href="{up}index.html">{SITE}</a>
  <form class="sform" role="search" autocomplete="off" onsubmit="return false">
    <input id="q" type="search" placeholder="英単語を入力（例: run, running）" aria-label="英単語を検索">
    <ul id="sug" class="sug" hidden></ul>
  </form>
</div></header>
<main class="wrap">
"""

def foot(up):
    return f"""</main>
<footer class="site-foot"><div class="wrap">
  <p><a href="{up}index.html">トップ</a> ・ <a href="{up}list/rank-1.html">頻度順リスト</a> ・ <a href="{up}about.html">このサイトについて・出典</a> ・ <a href="{up}privacy.html">プライバシーポリシー</a></p>
  <p class="small">語義: EJDict-hand（パブリックドメイン）／例文: Tatoeba（CC BY 2.0 FR）／語源: Wiktionary（CC BY-SA）／発音: CMUdict</p>
</div></footer>
<script src="{up}assets/search.js" defer></script>
</body></html>
"""

def write(path, content):
    p = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(content)

def hl(sentence, w, extra_forms):
    targets = {w} | forms(w) | extra_forms
    def rep(m):
        return f"<mark>{m.group(0)}</mark>" if m.group(0).lower() in targets else m.group(0)
    return re.sub(r"[A-Za-z]+", rep, esc(sentence, quote=False))

def level(r):
    if r <= 1000: return "最頻出"
    if r <= 3000: return "頻出"
    if r <= 6000: return "標準"
    return "やや難"

_ALPHA = {}
_ETYM = {}
_ETJA = {}

def load_etym_ja():
    if not _ETJA:
        d = {}
        import glob
        for f in sorted(glob.glob(os.path.join(ROOT, "tools", "content", "etym_ja*.json"))):
            d.update(json.load(open(f, encoding="utf-8")))
        _ETJA["d"] = d
    return _ETJA["d"]

def etym_html(w):
    if not _ETYM:
        f = os.path.join(DATA, "etymology.json")
        _ETYM["d"] = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
    t = _ETYM["d"].get(w, "").strip()
    ja = load_etym_ja().get(w)
    if not t and not ja: return ""
    t = re.sub(r"\s+", " ", t)
    if len(t) > 700:
        cut = t[:700]
        t = cut[:cut.rfind(". ") + 1] if ". " in cut[300:] else cut.rstrip() + "…"
    h = '<h2>語源</h2>\n'
    if ja:
        h += '<div class="etym ja">'
        if ja.get("parts"):
            h += '<p class="parts">' + '<span class="plus">＋</span>'.join(
                f'<span class="part"><b>{esc(x["p"])}</b><small>{esc(x["m"])}</small></span>' for x in ja["parts"]) + '</p>'
        h += f'<p class="story">{esc(ja["story"])}</p>'
        if ja.get("note"): h += f'<p class="small">{esc(ja["note"])}</p>'
        h += '</div>\n'
    if t:
        h += ('<details class="etym"><summary>英語の原文（Wiktionary）</summary><p lang="en">' + esc(t) + '</p>'
              f'<p class="src">出典: <a href="https://en.wiktionary.org/wiki/{w}#Etymology" rel="nofollow noopener">Wiktionary「{w}」</a>'
              '（<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja" rel="noopener">CC BY-SA 4.0</a>）</p></details>\n')
    return h

def word_page(x, words, order, pos, eng, pairs, form_of):
    w = x["w"]
    up = "../"
    summ = x["summary"]
    kt = KATA_WORDS.get(w)
    kmain = f"（{kt[0]}）" if kt else ""
    title = f"{w}{kmain}の意味・発音・例文・語源 | {SITE}"
    desc = f"英単語 {w}" + (f"（カタカナ語「{'・'.join(kt)}」）" if kt else "") + f" の意味は「{summ}」。" + (f"発音記号 /{x['ipa']}/。" if x["ipa"] else "") + "日本語訳つきの例文で使い方を確認できます。"
    ld = json.dumps({"@context": "https://schema.org", "@type": "DefinedTerm", "name": w,
                     "description": summ, "inLanguage": "en",
                     "inDefinedTermSet": f"{BASE_URL}/"}, ensure_ascii=False)
    h = head(title, desc, f"w/{w}.html", f'<script type="application/ld+json">{ld}</script>')
    h += f'<article class="entry"><p class="crumb"><a href="{up}index.html">トップ</a> › <a href="{up}list/{w[0]}.html">{w[0].upper()}</a> › {w}</p>\n'
    h += f'<h1>{w}{("<small>" + esc("・".join(kt)) + "</small>") if kt else ""}</h1>\n<p class="meta">'
    if x["ipa"]:
        h += f'<span class="ipa">/{esc(x["ipa"])}/</span> '
    h += f'<span class="tag">{level(x["rank"])}</span> <span class="rank">頻度 {x["rank"]}位</span></p>\n'
    if x["terms"]:
        h += f'<p class="core"><span>要点</span>{esc("、".join(x["terms"][:6]))}</p>\n'
    h += '<h2>意味</h2>\n'
    blocks = []
    for m in x["means"]:
        blocks += [b.strip() for b in m.split(" / ") if b.strip()]
    h += '<ol class="senses">\n'
    for b in blocks[:14]:
        parts = split_bullets(b)
        h += "<li>" + "<br>".join(fmt_sense(p) for p in parts[:10]) + "</li>\n"
    h += "</ol>\n"
    if len(blocks) > 14:
        h += '<p class="small">※ 一部の語義を省略しています。</p>\n'
    h += '<div class="adslot" data-slot="mid"></div>\n'
    if x["ex"]:
        fx = {f for f, b in form_of.items() if b == w}
        h += "<h2>例文</h2>\n<ul class=\"ex\">\n"
        for sid in x["ex"]:
            h += f'<li><p class="en">{hl(eng[sid], w, fx)}</p><p class="ja">{esc(pairs[sid])}</p><p class="src"><a href="https://tatoeba.org/ja/sentences/show/{sid}" rel="nofollow noopener">Tatoeba #{sid}</a></p></li>\n'
        h += "</ul>\n"
    h += etym_html(w)
    alpha0 = _ALPHA.setdefault("a", sorted(words))
    import bisect
    lo = bisect.bisect_left(alpha0, w)
    rel = []
    while lo < len(alpha0) and alpha0[lo].startswith(w) and len(rel) < 30:
        if alpha0[lo] != w and len(w) >= 3: rel.append(alpha0[lo])
        lo += 1
    rel = sorted(rel, key=lambda n: words[n]["rank"])[:8]
    alpha = _ALPHA.setdefault("a", sorted(words))
    k = _ALPHA.setdefault("p", {x: i for i, x in enumerate(alpha)})[w]
    neigh = [n for n in alpha[max(0, k - 3):k + 4] if n != w]
    if rel:
        h += '<h2>関連する単語</h2>\n<p class="chips">' + " ".join(f'<a href="{n}.html">{n}</a>' for n in rel) + "</p>\n"
    h += '<h2>辞書順で近い単語</h2>\n<p class="chips">' + " ".join(f'<a href="{n}.html">{n}</a>' for n in neigh) + "</p>\n"
    h += "</article>\n" + foot(up)
    return h

def build_site(words, eng, pairs, form_of):
    for sub in ("w", "list"):
        shutil.rmtree(os.path.join(OUT, sub), ignore_errors=True)
    order = sorted(words, key=lambda w: words[w]["rank"])
    pos = {w: i for i, w in enumerate(order)}
    for w in order:
        write(f"w/{w}.html", word_page(words[w], words, order, pos, eng, pairs, form_of))

    # 検索インデックス: [表記, 遷移先, 要約]
    idx = [[w, w, words[w]["summary"]] for w in order]
    for f, b in form_of.items():
        if b in words:
            idx.append([f, b, words[b]["summary"]])
    for w, ks in KATA_WORDS.items():
        if w in words:
            for k in ks:
                idx.append([k, w, words[w]["summary"]])
    idx.sort(key=lambda r: (words.get(r[1], {}).get("rank", 10**9), r[0]))
    write("assets/index.json", json.dumps(idx, ensure_ascii=False, separators=(",", ":")))

    # 頭文字別
    by = defaultdict(list)
    for w in sorted(words): by[w[0]].append(w)
    letters = sorted(by)
    for L in letters:
        h = head(f"{L.upper()} で始まる英単語一覧 | {SITE}", f"{L.upper()}で始まる英単語 {len(by[L])} 語の一覧。意味・発音・例文つき。", f"list/{L}.html")
        h += f"<h1>{L.upper()} で始まる英単語</h1>\n<p class=\"small\">{len(by[L])}語</p>\n<ul class=\"wl\">\n"
        for w in by[L]:
            h += f'<li><a href="../w/{w}.html"><b>{w}</b><span>{esc(words[w]["summary"])}</span></a></li>\n'
        h += "</ul>\n" + foot("../")
        write(f"list/{L}.html", h)
    # 頻度順
    step = 500
    bands = [order[i:i + step] for i in range(0, len(order), step)]
    for n, band in enumerate(bands, 1):
        a, b = (n - 1) * step + 1, (n - 1) * step + len(band)
        h = head(f"頻度 {a}〜{b} 位の英単語 | {SITE}", f"日常の英語でよく使われる順に並べた {a}〜{b} 位の英単語リスト。", f"list/rank-{n}.html")
        h += f"<h1>頻度 {a}〜{b} 位の英単語</h1>\n<p class=\"small\">例文コーパス(Tatoeba)での出現頻度順です。</p>\n"
        h += '<p class="chips">' + " ".join(f'<a href="rank-{k}.html"{" aria-current=page" if k == n else ""}>{(k-1)*step+1}〜</a>' for k in range(1, len(bands) + 1)) + "</p>\n"
        h += "<ol class=\"wl\" start=\"%d\">\n" % a
        for w in band:
            h += f'<li><a href="../w/{w}.html"><b>{w}</b><span>{esc(words[w]["summary"])}</span></a></li>\n'
        h += "</ol>\n" + foot("../")
        write(f"list/rank-{n}.html", h)

    # カタカナ語
    kw = sorted((w for w in KATA_WORDS if w in words), key=lambda w: words[w]["rank"])
    h = head(f"カタカナ語の英語一覧（{len(kw)}語）| {SITE}", "シャープ・サービス・ストライクなど、日本語でよく使うカタカナ語の英語の意味・発音・例文を一覧で調べられます。", "list/katakana.html")
    h += f"<h1>カタカナ語の英語</h1>\n<p class=\"small\">日本語で使うカタカナ語（{len(kw)}語）。英語の意味は、カタカナ語の意味と違うことがあります。</p>\n<ul class=\"wl\">\n"
    for w in kw:
        h += f'<li><a href="../w/{w}.html"><b>{esc("・".join(KATA_WORDS[w]))}</b><span>{w} — {esc(words[w]["summary"])}</span></a></li>\n'
    h += "</ul>\n" + foot("../")
    write("list/katakana.html", h)

    # トップ
    h = head(f"{SITE} — 広告の少ない、読みやすい英和辞書", f"英単語の意味・発音・例文をすばやく調べられる無料の英和辞書。{len(words)}語収録。", "")
    h += f"""<section class="hero">
<h1>{SITE}</h1>
<p>調べたい英単語を入力するだけ。意味・発音・日本語訳つきの例文まで、1ページで確認できます。</p>
<p class="small">カタカナ（シャープ、サービス など）でも検索できます。活用形（running など）は、もとの単語のページに案内します。</p>
</section>
<h2>よく使われる単語</h2>
<p class="chips">{" ".join(f'<a href="w/{w}.html">{w}</a>' for w in order[:80])}</p>
<h2>頻度順で探す</h2>
<p class="chips">{" ".join(f'<a href="list/rank-{k}.html">{(k-1)*step+1}〜{min(k*step, len(order))}位</a>' for k in range(1, len(bands)+1))}</p>
<h2>カタカナ語から探す</h2>
<p class="chips"><a href="list/katakana.html">カタカナ語の英語 一覧</a> {" ".join(f'<a href="w/{w}.html">{KATA_WORDS[w][0]}</a>' for w in kw[:24])}</p>
<h2>頭文字で探す</h2>
<p class="chips">{" ".join(f'<a href="list/{L}.html">{L.upper()}</a>' for L in letters)}</p>
"""
    h += foot("")
    write("index.html", h)

    about = head(f"このサイトについて・出典 | {SITE}", "データの出典とライセンス。", "about.html")
    about += f"""<h1>このサイトについて・出典</h1>
<p>{SITE}は、英単語の意味・発音・例文をすばやく調べるための無料の英和辞書です。個人が運営しています。</p>
<h2>データの出典</h2>
<ul>
<li><b>語義</b>: <a href="https://github.com/kujirahand/EJDict" rel="noopener">EJDict-hand</a>（パブリックドメイン／CC0）。収録語義は簡潔なため、辞書としての網羅性は市販の辞書に及びません。</li>
<li><b>例文</b>: <a href="https://tatoeba.org/" rel="noopener">Tatoeba</a> プロジェクトの投稿文（<a href="https://creativecommons.org/licenses/by/2.0/fr/" rel="noopener">CC BY 2.0 FR</a>）。各例文のリンクから原文と投稿者を確認できます。例文はユーザー投稿のため、不自然な表現を含む場合があります。</li>
<li><b>頻度</b>: Tatoeba の英文中の出現頻度から算出しています。一般的な英語全体の頻度とは異なる場合があります。</li>
<li><b>語源</b>: <a href="https://en.wiktionary.org/" rel="noopener">Wiktionary</a>（<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja" rel="noopener">CC BY-SA 4.0</a>）の語源欄を、加工せず原文（英語）のまま一部抜粋して掲載しています。各ページのリンクから原典と編集履歴を確認できます。</li>
<li><b>発音記号</b>: <a href="https://github.com/cmusphinx/cmudict" rel="noopener">CMU Pronouncing Dictionary</a>（米国発音）から自動変換しています。Copyright (C) 1993-2015 Carnegie Mellon University. All rights reserved.</li>
</ul>
<h2>広告について</h2>
<p>運営費をまかなうため、将来的に広告を表示することがあります。読みやすさを損なわないよう、表示は最小限にします。</p>
<h2>間違いを見つけたら</h2>
<p>語義や例文の誤りに気づいた場合は、<a href="https://github.com/kaitoinoue0921/eigo-tango/issues" rel="noopener">GitHubのIssue</a>からお知らせください。</p>
"""
    about += foot("")
    write("about.html", about)

    pv = head(f"プライバシーポリシー | {SITE}", "プライバシーポリシー", "privacy.html")
    pv += f"""<h1>プライバシーポリシー</h1>
<p>{SITE}（以下「当サイト」）は、以下のとおり利用者の情報を取り扱います。</p>
<h2>アクセス解析・広告について</h2>
<p>当サイトでは、Google 等の第三者配信事業者による広告（Google AdSense）やアクセス解析を導入する場合があります。これらはCookieを使用して、利用者の過去のアクセス情報に基づく広告の配信やアクセス状況の把握を行うことがあります。Cookieは、ブラウザの設定で無効にできます。詳細は <a href="https://policies.google.com/technologies/ads?hl=ja" rel="noopener">Googleの広告に関するポリシー</a> をご覧ください。</p>
<h2>検索について</h2>
<p>検索窓に入力した内容は、お使いのブラウザ内で処理され、当サイトのサーバーには送信されません。</p>
<h2>免責</h2>
<p>当サイトの情報の正確性には注意していますが、内容を保証するものではありません。利用により生じた損害について責任を負いかねます。</p>
<h2>お問い合わせ</h2>
<p><a href="https://github.com/kaitoinoue0921/eigo-tango/issues" rel="noopener">GitHubのIssue</a>からご連絡ください。</p>
"""
    pv += foot("")
    write("privacy.html", pv)

    urls = [""] + ["about.html", "privacy.html"] + [f"list/{L}.html" for L in letters] + ["list/katakana.html"] + \
           [f"list/rank-{n}.html" for n in range(1, len(bands) + 1)] + [f"w/{w}.html" for w in order]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sm += "".join(f"<url><loc>{BASE_URL}/{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    write("sitemap.xml", sm)
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")
    print("built", len(order), "words,", len(urls), "urls")

if __name__ == "__main__":
    main()
