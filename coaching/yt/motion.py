# -*- coding: utf-8 -*-
"""読み上げに合わせて、スライドの要素を順に出す（モーション）。
  1. mark_units(body)  … 本文の 箇条書き・表の行・ポイント枠・大文字の行・自由配置の要素 に data-rv=番号 を振る
  2. layers(...)       … 番号 k までを表示した画像を順に描き、前の画像との差分だけを透明PNGにする（= k 番目の要素だけの層）
  3. assign(units, sents, tp) … 各要素を、内容が似ている読み上げ文に結びつけ、出す時刻を決める
  動画では、土台（最初の要素まで）に、各層を「ふわっと下から」重ねる（vkit.encode_subtitled の layers）。
"""
import json, os, re
from PIL import Image, ImageChops

FADE = 0.35          # 出てくるまでの秒
RISE = 26            # 下から上がる距離 px
GAP = 0.55           # 同じ文に複数の要素が付いたときの間隔

_TAG = re.compile(r"<(li|tr|p|h2|h3|div class='key'|div class='big'|div class='ov(?:\s[^']*)?')(\s[^>]*)?>", re.S)
_CLOSE = {"li": "</li>", "tr": "</tr>", "p": "</p>", "h2": "</h2>", "h3": "</h3>", "div": "</div>", "span": "</span>"}

def _plain(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()

def mark_units(body):
    """data-rv を振った本文と、要素ごとの文字列（照合用）を返す。要素が1つ以下なら (body, [])"""
    if not body or "class='photo'" in body: return body, []
    # 大文字の場面: <br> で区切った行ごとに
    def huge(m):
        inner = m.group(2)
        lines = re.split(r"<br\s*/?>", inner)
        return m.group(1) + "<br>".join(f"<span class='rvl'>{l}</span>" for l in lines) + "</div>"
    body = re.sub(r"(<div class='huge'[^>]*>)(.*?)</div>", huge, body, flags=re.S)
    units, out, pos, n = [], [], 0, 0
    tag_re = re.compile(r"<(li|tr|p|h2|h3|span class='rvl'|div class='key'|div class='big'|div class='ov(?:\s[^']*)?')(\s[^>]*)?>", re.S)
    for m in tag_re.finditer(body):
        if m.start() < pos: continue                                   # 入れ子で既に処理した範囲
        kind = m.group(1).split(" ")[0].split("=")[0]
        close = _CLOSE.get(kind, "</div>")
        end = body.find(close, m.end())
        if end < 0: continue
        seg = body[m.end(): end]
        if kind == "tr" and re.search(r"<td", seg) is None: continue   # 見出し行（th だけ）は最初から出す
        if kind == "p" and "class='note'" in m.group(0): continue        # 注記は最初から
        if kind == "li" and "<li" in seg: continue
        text = _plain(seg)
        if not text and kind != "div": continue
        out.append(body[pos: m.start()])
        tag = m.group(0)
        if kind == "span": tag = tag.replace("class='rvl'", f"class='rvl' data-rv='{n}'")
        else: tag = tag[:-1] + f" data-rv='{n}'>"
        out.append(tag); pos = m.end(); units.append(text); n += 1
        if kind in ("li", "tr"):                                       # 中身は入れ子を見ない
            out.append(body[pos: end]); pos = end
    out.append(body[pos:])
    marked = "".join(out)
    if len(units) < 2: return body, []
    return marked, units

def hide_css(k):
    """k 番目以降の要素を隠す CSS（位置は変えない）。表の行は罫線と背景も消す（空の枠が見えないように）"""
    sel = ",".join(f"[data-rv='{j}']" for j in range(k, 400))
    cells = ",".join(f"tr[data-rv='{j}'] td,tr[data-rv='{j}'] th" for j in range(k, 400))
    return f"{sel}{{visibility:hidden}} {cells}{{border-color:transparent;background:transparent}}"

def diff_layer(prev_png, cur_png, out_png):
    """cur と prev の違う所だけを残した透明PNG（違う範囲に切り詰め、位置は .json に）。何も違わなければ None"""
    a = Image.open(prev_png).convert("RGB"); b = Image.open(cur_png).convert("RGB")
    if a.size != b.size:
        h = min(a.size[1], b.size[1]); a = a.crop((0, 0, a.size[0], h)); b = b.crop((0, 0, b.size[0], h))
    mask = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 6 else 0)
    bb = mask.getbbox()
    if not bb: return None
    x0, y0 = max(0, bb[0] - 4), max(0, bb[1] - 4); x1, y1 = min(b.size[0], bb[2] + 4), min(b.size[1], bb[3] + 4)
    layer = b.crop((x0, y0, x1, y1)).convert("RGBA"); layer.putalpha(mask.crop((x0, y0, x1, y1))); layer.save(out_png)
    json.dump({"x": x0, "y": y0}, open(out_png + ".json", "w"))
    return out_png

def offset(png):
    try: j = json.load(open(png + ".json")); return int(j["x"]), int(j["y"])
    except Exception: return 0, 0


def _bigrams(s):
    s = re.sub(r"[\s【】「」『』（）()、。・：:／/／\-ー〜~…※■□●○◎①-⑳※▼▲]", "", s)
    s = s.translate(str.maketrans("０１２３４５６７８９，", "0123456789,"))
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else set()

def assign(units, sents, tp, total):
    """要素 i → 出す時刻。0番目は最初から。内容が似た文の頭で出す（順番は前後しない）。似た文がなければ均等に"""
    n = len(units); m = len(sents)
    if n < 2 or m == 0: return []
    starts = [float(tp.get(f"s{j}", 0.0)) for j in range(m)]
    ub = [_bigrams(u) for u in units]; sb = [_bigrams(re.sub(r"[【】]", "", s)) for s in sents]
    pick, jprev = [0] * n, 0
    for i in range(1, n):
        best, bj = 0.0, None
        for j in range(jprev, m):
            if not ub[i]: break
            sc = len(ub[i] & sb[j]) / len(ub[i])
            if sc > best + 1e-9: best, bj = sc, j
        if bj is None or best < 0.18: bj = max(jprev, min(m - 1, round(i * (m - 1) / max(1, n - 1))))
        pick[i] = bj; jprev = bj
    times, last_j, k_in = [], -1, 0
    for i in range(1, n):
        j = pick[i]
        k_in = k_in + 1 if j == last_j else 0; last_j = j
        nxt = starts[j + 1] if j + 1 < m else total
        t = min(starts[j] + 0.15 + GAP * k_in, max(starts[j] + 0.15, nxt - FADE - 0.2))
        if times and t < times[-1] + 0.25: t = times[-1] + 0.25
        times.append(round(min(t, max(0.0, total - FADE - 0.3)), 2))
    return times            # 要素 1..n-1 の時刻

def save_units(path, units): json.dump(units, open(path, "w", encoding="utf-8"), ensure_ascii=False)
def load_units(path):
    try: return json.load(open(path, encoding="utf-8"))
    except Exception: return None
