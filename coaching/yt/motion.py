# -*- coding: utf-8 -*-
"""読み上げに合わせたモーション。
  ・要素（箇条書き・表の行・ポイント枠・大文字の行・自由配置）が、内容の似た文の頭で ふわっと下から出る
  ・話している行（表の行・箇条書き・大文字の行）に黄色いマーカー
  ・波線・赤枠は、要素が出たあとに左から描かれる
  ・数字（2桁以上）はカウントアップ
  仕組み: 要素を k 番目まで表示した画像を順に描き、前との差分を透明PNG（層）にして ffmpeg で重ねる。
  層と位置は描画キャッシュ (_rc/<ck>.motion.json と PNG) に残す。
  build(...) 側は plan(manifest, times, total) が返す ops を vkit.encode_subtitled(layers=ops) に渡すだけ。
"""
import json, os, re, shutil
from PIL import Image, ImageChops

FADE = 0.35          # 出てくるまでの秒
RISE = 26            # 下から上がる距離 px
GAP = 0.55           # 同じ文に複数の要素が付いたときの間隔
DRAW = 0.5           # 波線・枠を描く秒
COUNT_STEPS = 5      # カウントアップの段数
COUNT_DT = 0.14      # 1段の秒
HL_KINDS = ("tr", "li", "span")                      # マーカーを付ける種類（span = 大文字の行）
HL_COLOR = "0xFFE14D@0.30"

_CLOSE = {"li": "</li>", "tr": "</tr>", "p": "</p>", "h2": "</h2>", "h3": "</h3>", "div": "</div>", "span": "</span>"}
_NUM = re.compile(r"(?<![\d,.])(\d{1,3}(?:,\d{3})+|\d{2,})(?![\d,])(?=(?:\.\d+)?)")

def _plain(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()

def mark_units(body):
    """data-rv を振った本文と、要素の一覧 [{text, kind, start, end}]（start/end は印を付けた本文の中の中身の範囲）。要素が1つ以下なら (body, [])"""
    if not body or "class='photo'" in body: return body, []
    def huge(m):
        lines = re.split(r"<br\s*/?>", m.group(2))
        return m.group(1) + "<br>".join(f"<span class='rvl'>{l}</span>" for l in lines) + "</div>"
    body = re.sub(r"(<div class='huge'[^>]*>)(.*?)</div>", huge, body, flags=re.S)
    tag_re = re.compile(r"<(li|tr|p|h2|h3|span class='rvl'|div class='key'|div class='big'|div class='ov(?:\s[^']*)?')(\s[^>]*)?>", re.S)
    units, out, pos, n, shift = [], [], 0, 0, 0
    for m in tag_re.finditer(body):
        if m.start() < pos: continue
        kind = m.group(1).split(" ")[0].split("=")[0]
        close = _CLOSE.get(kind, "</div>")
        end = body.find(close, m.end())
        if end < 0: continue
        seg = body[m.end(): end]
        if kind == "tr" and re.search(r"<td", seg) is None: continue
        if kind == "p" and "class='note'" in m.group(0): continue
        if kind == "li" and "<li" in seg: continue
        text = _plain(seg)
        if not text and kind != "div": continue
        out.append(body[pos: m.start()])
        tag = m.group(0)
        tag = tag.replace("class='rvl'", f"class='rvl' data-rv='{n}'") if kind == "span" else tag[:-1] + f" data-rv='{n}'>"
        out.append(tag)
        shift += len(tag) - len(m.group(0))
        units.append({"text": text, "kind": kind, "start": m.end() + shift, "end": end + shift,
                      "deco": bool(re.search(r"<b[\s>]|class='rbox'", seg)),
                      "nums": [x for x in _NUM.findall(_plain(seg)) if _countable(x, text)][:3]})
        pos = m.end(); n += 1
        if kind in ("li", "tr"): out.append(body[pos: end]); pos = end
    out.append(body[pos:])
    marked = "".join(out)
    if len(units) < 2: return body, []
    return marked, units

def _countable(num, text):
    v = int(num.replace(",", ""))
    if v < 10 or v == 10 ** (len(str(v)) - 1): return False                  # 1桁、10/100/1000 は動かしても同じ幅にならない
    i = text.find(num)
    after = text[i + len(num): i + len(num) + 1] if i >= 0 else ""
    if after in ("年", "月", "日", "時", "条", "号") or (1900 <= v <= 2100): return False   # 年号・日付・条文は数えない
    return True

def hide_css(k, nodeco=None):
    """k 番目以降の要素を隠す CSS（位置は変えない）。表の行は罫線と背景も消す。nodeco=k で k 番目の波線・赤枠だけ消す"""
    sel = ",".join(f"[data-rv='{j}']" for j in range(k, 400))
    cells = ",".join(f"tr[data-rv='{j}'] td,tr[data-rv='{j}'] th" for j in range(k, 400))
    css = f"{sel}{{visibility:hidden}} {cells}{{border-color:transparent;background:transparent}}"
    if nodeco is not None:
        css += (f" [data-rv='{nodeco}'] b,[data-rv='{nodeco}'].rvl b{{text-decoration:none}}"
                f" [data-rv='{nodeco}'] .rbox,[data-rv='{nodeco}'].rbox{{border-color:transparent}}")
    return css

def diff_layer(prev_png, cur_png, out_png, pad=4):
    """cur と prev の違う所だけを残した透明PNG（違う範囲に切り詰める）。(x, y, w, h) を返す。違いがなければ None"""
    a = Image.open(prev_png).convert("RGB"); b = Image.open(cur_png).convert("RGB")
    if a.size != b.size:
        h = min(a.size[1], b.size[1]); a = a.crop((0, 0, a.size[0], h)); b = b.crop((0, 0, b.size[0], h))
    mask = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 6 else 0)
    bb = mask.getbbox()
    if not bb: return None
    x0, y0 = max(0, bb[0] - pad), max(0, bb[1] - pad); x1, y1 = min(b.size[0], bb[2] + pad), min(b.size[1], bb[3] + pad)
    layer = b.crop((x0, y0, x1, y1)).convert("RGBA"); layer.putalpha(mask.crop((x0, y0, x1, y1))); layer.save(out_png)
    return [x0, y0, x1 - x0, y1 - y0]

def _step_values(num):
    v = int(num.replace(",", "")); d = len(str(v)); lo = 10 ** (d - 1)
    vals = [lo + int((v - lo) * f) for f in (0.0, 0.3, 0.55, 0.78, 0.92)]
    return [f"{x:,}" if "," in num else str(x) for x in vals]

def count_body(marked, u, step):
    """要素 u の数字を step 段目の値に差し替えた本文"""
    seg = marked[u["start"]: u["end"]]
    for num in u["nums"]:
        seg = re.sub(r"(?<![\d,])" + re.escape(num) + r"(?![\d,])", _step_values(num)[step], seg, count=1)
    return marked[: u["start"]] + seg + marked[u["end"]:]

def build_layers(render_once, head, body, name, scale, cdir, ck, W, H):
    """全部の層を描いてマニフェストを返す（キャッシュがあればそれ）。render_once(head, body, name, scale, extra_css) -> (PIL image, ...)"""
    man_p = os.path.join(cdir, ck + ".motion.json")
    marked, units = mark_units(body)
    if not units: return None
    man = _load(man_p)
    if man and man.get("ver") == 3 and [u["text"] for u in man["units"]] == [u["text"] for u in units] and \
       all(os.path.exists(os.path.join(cdir, f)) for f in man.get("files", [])):
        return man
    files, prev = [], None
    def snap(k, tag, extra):
        im, _ch, _p = render_once(head, extra.get("body", marked), f"{name}_{tag}", scale, extra["css"])
        p = os.path.join(cdir, f"{ck}_{tag}.png"); im.crop((0, 0, W, min(im.size[1], H))).save(p); return p
    s_all_hidden = snap(-1, "mh", {"css": hide_css(0)})
    out_units = []
    for k, u in enumerate(units):
        rec = {"text": u["text"], "kind": u["kind"]}
        if u["deco"]:
            nod = snap(k, f"mn{k}", {"css": hide_css(k + 1, nodeco=k)})
            full = snap(k, f"m{k}", {"css": hide_css(k + 1)})
            base_prev = prev if prev else s_all_hidden
            if k > 0:
                lp = f"{ck}_u{k}.png"; bb = diff_layer(base_prev, nod, os.path.join(cdir, lp))
                if bb: rec["layer"], rec["box"] = lp, bb; files.append(lp)
            else:
                bb = diff_layer(s_all_hidden, nod, os.path.join(cdir, f"{ck}_tmp.png"))
                if bb: rec["box"] = bb
            dp = f"{ck}_d{k}.png"; dbb = diff_layer(nod, full, os.path.join(cdir, dp), pad=6)
            if dbb: rec["deco"], rec["dbox"] = dp, dbb; files.append(dp)
            cur = full
        else:
            cur = snap(k, f"m{k}", {"css": hide_css(k + 1)})
            base_prev = prev if prev else s_all_hidden
            if k > 0:
                lp = f"{ck}_u{k}.png"; bb = diff_layer(base_prev, cur, os.path.join(cdir, lp))
                if bb: rec["layer"], rec["box"] = lp, bb; files.append(lp)
            else:
                bb = diff_layer(s_all_hidden, cur, os.path.join(cdir, f"{ck}_tmp.png"))
                if bb: rec["box"] = bb
        if u["nums"] and rec.get("box"):
            steps = []
            for i in range(COUNT_STEPS):
                sp = snap(k, f"mc{k}_{i}", {"css": hide_css(k + 1), "body": count_body(marked, u, i)})
                cp = f"{ck}_c{k}_{i}.png"; cbb = diff_layer(cur, sp, os.path.join(cdir, cp), pad=3)
                if not cbb or cbb[2] > W * 0.35 or cbb[3] > max(140, rec["box"][3] * 1.5): steps = []; break
                steps.append({"png": cp, "box": cbb})
            if steps: rec["count"] = steps; files += [s["png"] for s in steps]
        if k == 0: shutil.copy(cur, os.path.join(cdir, f"{ck}_u0.png")); files.append(f"{ck}_u0.png")
        out_units.append(rec); prev = cur
    man = {"ver": 3, "units": out_units, "files": files, "base": f"{ck}_u0.png"}
    json.dump(man, open(man_p, "w", encoding="utf-8"), ensure_ascii=False)
    return man

def _bigrams(s):
    s = re.sub(r"[\s【】「」『』（）()、。・：:／/\-ー〜~…※■□●○◎①-⑳▼▲]", "", s)
    s = s.translate(str.maketrans("０１２３４５６７８９，", "0123456789,"))
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else set()

def assign(units, sents, tp, total):
    """要素 i → 出す時刻（要素 0 は 0.0）。内容が似た文の頭で出す（順番は前後しない）。似た文がなければ均等に"""
    texts = [u["text"] if isinstance(u, dict) else u for u in units]
    n = len(texts); m = len(sents)
    if n < 1 or m == 0: return [0.0] * n
    starts = [float(tp.get(f"s{j}", 0.0)) for j in range(m)]
    ub = [_bigrams(u) for u in texts]; sb = [_bigrams(re.sub(r"[【】]", "", s)) for s in sents]
    pick, jprev = [0] * n, 0
    for i in range(1, n):
        best, bj = 0.0, None
        for j in range(jprev, m):
            if not ub[i]: break
            sc = len(ub[i] & sb[j]) / len(ub[i])
            if sc > best + 1e-9: best, bj = sc, j
        if bj is None or best < 0.18: bj = max(jprev, min(m - 1, round(i * (m - 1) / max(1, n - 1))))
        pick[i] = bj; jprev = bj
    times, last_j, k_in = [0.0], -1, 0
    for i in range(1, n):
        j = pick[i]
        k_in = k_in + 1 if j == last_j else 0; last_j = j
        nxt = starts[j + 1] if j + 1 < m else total
        t = min(starts[j] + 0.15 + GAP * k_in, max(starts[j] + 0.15, nxt - FADE - 0.2))
        if t < times[-1] + 0.25: t = times[-1] + 0.25
        times.append(round(min(t, max(0.0, total - FADE - 0.3)), 2))
    return times

def plan(man, times, total, cdir):
    """マニフェスト + 出す時刻 → vkit.encode_subtitled に渡す ops"""
    ops, units = [], man["units"]
    for k, u in enumerate(units):
        t = times[k] if k < len(times) else 0.0
        t_next = times[k + 1] if k + 1 < len(times) else total
        if k > 0 and u.get("layer"):
            x, y, _w, _h = u["box"]
            ops.append({"type": "fade", "png": os.path.join(cdir, u["layer"]), "t": t, "x": x, "y": y})
        if u.get("deco"):
            x, y, _w, _h = u["dbox"]
            ops.append({"type": "wipe", "png": os.path.join(cdir, u["deco"]), "t": t + (FADE if k > 0 else 0.3), "d": DRAW, "x": x, "y": y})
        if u.get("count"):
            t0 = t + (0.2 if k > 0 else 0.3)
            for i, st in enumerate(u["count"]):
                x, y, _w, _h = st["box"]
                ops.append({"type": "step", "png": os.path.join(cdir, st["png"]), "t0": t0 + i * COUNT_DT, "t1": t0 + (i + 1) * COUNT_DT, "x": x, "y": y})
        if u.get("kind") in HL_KINDS and u.get("box") and t_next - t > 0.8:
            x, y, w, h = u["box"]
            ops.append({"type": "box", "x": x, "y": y, "w": w, "h": h, "t0": t + (FADE if k > 0 else 0.3), "t1": max(t + FADE + 0.3, t_next - 0.1), "color": HL_COLOR})
    return ops

def _load(p):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return None
