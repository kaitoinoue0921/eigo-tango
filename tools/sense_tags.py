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
# EJDictの交ぜ書き → 例文の和訳でふつうに使われる表記
MAZEGAKI = {"ざん新": "斬新", "ばく大": "莫大", "ぜい弱": "脆弱", "そ外": "疎外", "けん引": "牽引", "ねつ造": "捏造",
            "破たん": "破綻", "改ざん": "改竄", "ら致": "拉致", "だ円": "楕円", "かく乱": "撹乱", "ひ弊": "疲弊",
            "ごう慢": "傲慢", "ぶ然": "憮然", "ぼう大": "膨大", "せん越": "僭越", "だ落": "堕落", "ろう下": "廊下",
            "き弁": "詭弁", "ひ護": "庇護", "しっ責": "叱責", "ばん回": "挽回", "はく奪": "剥奪", "ほう助": "幇助",
            "けい動脈": "頸動脈", "そ上": "遡上", "ちゅう躇": "躊躇", "ちょう笑": "嘲笑", "ひん死": "瀕死",
            "えん恨": "怨恨", "おう吐": "嘔吐", "がい骨": "骸骨", "かい離": "乖離", "かっ色": "褐色", "き章": "徽章",
            "きゅう覚": "嗅覚", "けい光": "蛍光", "こう配": "勾配", "こん睡": "昏睡", "さい疑": "猜疑", "し好": "嗜好",
            "しっ病": "疾病", "じゅう器": "什器", "しゅん工": "竣工", "せん孔": "穿孔", "そ略": "粗略", "たい積": "堆積",
            "ちつ序": "秩序", "てん末": "顛末", "とう汰": "淘汰", "どん欲": "貪欲", "ねん挫": "捻挫", "はん用": "汎用",
            "ひっ迫": "逼迫", "ふん囲気": "雰囲気", "へき地": "僻地", "ぼっ興": "勃興", "まん延": "蔓延", "ゆ着": "癒着",
            "らん用": "濫用", "り患": "罹患", "ろう城": "籠城", "わい曲": "歪曲", "わん曲": "湾曲"}


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
    for k, v in MAZEGAKI.items(): block = block.replace(k, v)
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


DET = {"a", "an", "the", "its", "his", "her", "my", "your", "our", "their", "this", "these", "those", "no", "every", "each"}
AUX_NEXT = {"is", "was", "are", "were", "will", "would", "can", "could", "has", "had", "have", "went", "goes", "came", "comes", "of"}
VERB_PREV = {"to", "will", "would", "can", "could", "should", "must", "may", "might", "please", "did", "didn't", "don't", "doesn't", "not", "i", "we", "they"}


def pos_fits(word, en, pos):
    """英文の中の word の使われ方が品詞 pos（名詞・動詞…）と矛盾しないか。どれか1か所でも合えば True。"""
    if pos not in ("名詞", "動詞", "形容詞", "副詞"): return True
    toks = re.findall(r"[A-Za-z']+|[.,!?;:]", en.lower())
    w = word.lower(); hit = False
    for i, t in enumerate(toks):
        if not (t == w or (t.startswith(w) and len(t) - len(w) <= 3 and t[len(w):] in ("s", "es", "ed", "d", "ing", "er", "est", "ly"))): continue
        hit = True
        prev = toks[i - 1] if i else ""; nxt = toks[i + 1] if i + 1 < len(toks) else "."
        if pos == "動詞" and (prev in DET or nxt in AUX_NEXT): continue
        if pos == "名詞" and prev in VERB_PREV: continue
        if pos in ("形容詞", "副詞") and prev in DET and (nxt in AUX_NEXT or nxt in ".,!?;:"): continue
        if pos == "副詞" and prev in DET: continue
        return True
    return not hit  # 見出し語が英文に見つからない（不規則変化など）ときは判定しない


def match_sense(ja, blocks, en=None, word=None, pos=None):
    """例文の和訳と一番よく一致する語義ブロックの番号。決められなければ -1。
    en・word・pos（ブロックごとの品詞）があれば、英文での品詞と合わない語義は選ばない。"""
    best, best_i = 0, -1
    for i, b in enumerate(blocks):
        if pos and en and i < len(pos) and not pos_fits(word, en, pos[i]): continue
        core = re.findall(r"『([^』]+)』", b)
        for t in _terms(b):
            n = _match_len(t, ja)
            if n and any(t in c for c in core): n += 0.5  # 核になる訳語を優先
            if n > best: best, best_i = n, i
    return best_i
