"""EJDictの語義ブロックに品詞を付け、例文がどの語義で使われているかを推定する。

EJDictには品詞欄がないので、語義の日本語の形（〈C〉〈U〉、…を、〜する、〜な 等）から推定し、
WordNetと機能語リストから作った品詞一覧（data/pos_wikt.json、make_pos.py）にない品詞は選ばないよう絞り込む。
"""
import json, os, re

POS_JA = {"noun": "名詞", "verb": "動詞", "adj": "形容詞", "adv": "副詞", "prep": "前置詞",
          "conj": "接続詞", "pron": "代名詞", "det": "形容詞", "intj": "間投詞", "num": "数詞"}
_WIKT_MAP = {"noun": "noun", "verb": "verb", "adj": "adj", "adv": "adv", "prep": "prep",
             "conj": "conj", "pron": "pron", "det": "det", "article": "det", "intj": "intj", "num": "num"}
HIRA = re.compile(r"[ぁ-ゖ]")
KANJI = re.compile(r"[一-鿿々]")


def load_wikt(data_dir):
    p = os.path.join(data_dir, "pos_wikt.json")
    if not os.path.exists(p): return {}
    out = {}
    for w, cnt in json.load(open(p, encoding="utf-8")).items():
        c = {}
        for k, v in cnt.items():
            if k in _WIKT_MAP: c[_WIKT_MAP[k]] = c.get(_WIKT_MAP[k], 0) + v
        out[w] = c
    return out


def adjective_stems(all_means):
    """「軽く」を副詞と判定するため、EJDict中の『〜い』形容詞の語幹を集める。"""
    s = set()
    for m in all_means:
        for t in re.findall(r"『([^』]+?)い』", m):
            if KANJI.search(t): s.add(t)
    return s


def _core(block):
    t = re.sub(r"《[^》]*》|\([^)]*\)|（[^）]*）|\[[^\]]*\]|〈[^〉]*〉", "", block)
    t = t.replace("『", "").replace("』", "").strip()
    return t


CONJ_END = re.compile(r"(ので|だから|けれど|けれども|ても|とき|時|ならば|なら|ために|ということ|かどうか|ほど|間|以上|一方|た後で|た後に|てから)$")


def guess(block, adj_stems, prep_word=False):
    if re.search(r"〈[CU]〉", block): return "noun"
    if re.search(r"be動詞|^beの|の過去|過去分詞|現在分詞|三人称単数|一人称単数", block): return "verbform"
    if re.search(r"《[^》]*(節を導|接続詞)", block): return "conj"
    if re.search(r"《[^》]*関係代名詞|《[^》]*代名詞", block): return "pron"
    if re.search(r"《[^》]*(補語にのみ|補語として|名詞の前にのみ|限定的に|叙述的に)", block): return "adj"
    core = _core(block)
    if not core.strip("…;,、 "): return None  # 《時間》のような小見出しだけのブロック
    if re.search(r"《[^》]*(驚|表して|呼びかけ|間投詞)", block) and re.fullmatch(r"[ぁ-ゖァ-ヶー,;、!！?？]{1,12}", core):
        return "intj"
    if core.startswith("…") and CONJ_END.search(re.split(r"[,;、・]", core)[0].strip()): return "conj"
    if prep_word and core.startswith("…"): return "func"
    if re.search(r"〈[^〉]*が〉|〈[^〉]*〉を", block): return "verb"
    if core.startswith(("…を", "を")): return "verb"
    if core.startswith("…") and re.search(r"(に|で|から|へ|まで|について|として|より|の間に|によって|において)$",
                                          re.split(r"[,;、・]", core)[0].strip()):
        return "func"
    items = [x.strip().strip("…") for x in re.split(r"[,;、・]", core) if x.strip().strip("…")]
    for head in items:
        g = _guess_head(head, adj_stems)
        if g: return g
    return "noun"


def _guess_head(head, adj_stems):
    for suf, p in (("ている", "stative"), ("でいる", "stative"), ("させる", "verb"), ("される", "verb"), ("する", "verb"), ("的な", "adj"),
                   ("ように", "adv"), ("のある", "adj"), ("のない", "adj")):
        if head.endswith(suf): return p
    if head.endswith(("こと", "もの", "ところ")): return "noun"
    last = head[-1]
    prev = head[-2] if len(head) > 1 else ""
    if last in "なの": return "adj"
    if last == "い" and len(head) > 1: return "adj"
    if last == "た" and len(head) > 1: return "adj"
    if last == "く" and (head[:-1] in adj_stems or HIRA.match(prev or "")): return "adv"
    if last in "にとて" and len(head) > 1: return "adv"
    if last in "うくすつぬふむぶぐる" and len(head) > 1: return "verb"
    return None


def tag_blocks(word, blocks, wikt, adj_stems):
    """各語義ブロックの品詞（日本語ラベル）のリストを返す。判定できなければ空文字。"""
    allowed = wikt.get(word) or {}
    total = sum(allowed.values()) or 1
    prep_word = allowed.get("prep", 0) / total >= 0.3
    raw = [guess(b, adj_stems, prep_word) for b in blocks]
    for i in range(len(raw) - 2, -1, -1):  # 小見出しは次の語義の品詞に合わせる
        if raw[i] is None: raw[i] = raw[i + 1]
    out, prev = [], None
    for g in raw:
        p = g
        if g == "stative":  # 「開いている」等は前の語義が形容詞ならその続き
            p = "adj" if prev == "adj" else "verb"
        if g == "verbform": p = g = "verb"; allowed = {**allowed, "verb": 1} if allowed else allowed
        if g == "intj": allowed = {**allowed, "intj": 1} if allowed else allowed
        if g == "func":
            p = next((k for k in ("prep", "conj", "adv") if k in allowed), "prep" if not allowed else None)
        if allowed and p not in allowed:
            # 品詞一覧にない品詞は選ばない。直前と同じ品詞→語義数が多い品詞の順で寄せる
            if g in ("noun", "adv") and "pron" in allowed: p = "pron"
            elif g == "adj" and "det" in allowed: p = "det"
            elif g == "adj" and "noun" in allowed and prev == "noun": p = "noun"
            elif prev in allowed: p = prev
            else: p = max(allowed, key=allowed.get)
        out.append("冠詞" if word in ("a", "an", "the") else POS_JA.get(p, ""))
        prev = p
    return out


def _terms(block):
    t = re.sub(r"《[^》]*》|\([^)]*\)|（[^）]*）|\[[^\]]*\]|〈[^〉]*〉|…", "", block).replace("『", "").replace("』", "")
    return [x.strip() for x in re.split(r"[,;、・/]", t) if len(x.strip()) >= 1]


def _match_len(term, ja):
    """語義の訳語が例文の和訳に出てくるかを、活用を考えて調べ、一致した長さを返す。"""
    if not re.search(r"[一-鿿々ァ-ヶ]", term) and len(term) < 4: return 0  # 「なる」等は誤一致が多い
    if len(term) >= 2 and term in ja: return len(term)
    if term[-1] not in "うくすつぬふむぶぐるい": return 0
    stem = term[:-1]
    if not stem: return 0
    if len(stem) >= 2 and stem in ja: return len(stem)
    if len(stem) == 1 and KANJI.match(stem):
        i = ja.find(stem)
        while i >= 0:
            if i + 1 < len(ja) and HIRA.match(ja[i + 1]) and not (i > 0 and KANJI.match(ja[i - 1])): return 1
            i = ja.find(stem, i + 1)
    return 0


def match_sense(ja, blocks):
    """例文の和訳と一番よく一致する語義ブロックの番号。決められなければ -1。"""
    best, best_i = 0, -1
    for i, b in enumerate(blocks):
        core = re.findall(r"『([^』]+)』", b)
        for t in _terms(b):
            n = _match_len(t, ja)
            if n and any(t in c for c in core): n += 0.5  # 核になる訳語を優先
            if n > best: best, best_i = n, i
    return best_i
