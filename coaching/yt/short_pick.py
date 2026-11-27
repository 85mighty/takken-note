# -*- coding: utf-8 -*-
"""長い動画（本編）から、ショートを作る。
  python3 short_pick.py specs/R8_xxx.json [--n 2]          … 既定: キーワードごとに「ショート専用の台本」を新しく書いて作る
  python3 short_pick.py specs/R8_xxx.json [--n 2] --pick   … 以前の方式: 本編のスライドを1枚選んで切り出す
  既定の方式（2026-11-22〜、docs/SHORTS_RULES.md §7）:
    Claude に本編の内容を渡し、ショート向きのキーワードを n 個選ばせて、1枚の専用スライド（表＋ひとこと）と 40〜55 秒の読み上げを書かせる。
    specs/SHORT_<本編名>_<slug>.json（short_target=本編）として保存し、shorts.py で縦動画にする。本編にない数字・事実は書かせない。
  Claude が使えないときは、以前の方式（スライドを選ぶ）に戻る。
"""
import argparse, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

def _plain(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()

def heuristic(spec):
    """Claude なしの選び方: 数字・結論・表・大文字に点、表紙とまとめは外す"""
    best = []
    for i, s in enumerate(spec["slides"], 1):
        body, title = s.get("body", ""), s.get("title", "")
        if not title or s.get("photo") or "class='cover'" in body: continue
        sc = 0
        sc += 3 if "結論" in title else 0
        sc += 2 if "<table" in body else 0
        sc += 2 if "class='huge'" in body else 0
        sc += min(3, len(re.findall(r"\d{2,}", _plain(body))))
        sc += 1 if "class='key'" in body else 0
        sc -= 2 if "まとめ" in title else 0
        sc -= 1 if i == len(spec["slides"]) else 0
        best.append((sc, -i, i))
    best.sort(reverse=True)
    return [b[2] for b in best]

def ask(spec, n, log=print):
    import scriptgen
    if not scriptgen.available(): return None
    rows = []
    for i, s in enumerate(spec["slides"], 1):
        rows.append(f"[{i}] 見出し: {s.get('title') or '（表紙）'}\n本文: {_plain(s.get('body',''))[:220]}\n読み上げ: {(s.get('speech') or '')[:160]}")
    prompt = (f"動画「{spec.get('label','')}」のスライド一覧です。YouTube ショート（60秒・縦）として切り出したとき、最も再生されそうな（意外性・数字・結論がある）スライドを {n} 枚選び、"
              f"それぞれに視聴者の指を止めるフック（日本語・2行・各行12字以内・疑問形か断定形。合格率・点数・金額・時間などの数字があれば必ず1行目に入れる。改行は \\n）と、"
              f"概要欄に載せる1行（desc: 日本語 30〜60字・1文・その場面で分かることを具体的に。「2つめ、実務です」のようなつなぎの文は不可。リンク・タグ・絵文字なし）を付けてください。表紙・まとめ・写真だけの場面は選ばない。\n\n" + "\n\n".join(rows))
    schema = {"type": "object", "additionalProperties": False, "required": ["picks"],
              "properties": {"picks": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["i", "hook", "desc", "reason"],
                                        "properties": {"i": {"type": "integer"}, "hook": {"type": "string"}, "desc": {"type": "string"}, "reason": {"type": "string"}}}}}}
    def check(o):
        ps = o.get("picks") or []
        if not ps: return "picks が空です"
        for p in ps:
            if not (1 <= int(p.get("i", 0)) <= len(spec["slides"])): return f"i={p.get('i')} は範囲外です"
            if not str(p.get("hook", "")).strip(): return "hook が空です"
            if len(str(p.get("desc", "")).strip()) < 15: return "desc が短すぎます（30〜60字の1文）"
        return None
    try:
        o = scriptgen.ask_json(prompt, "あなたはYouTubeショートの編集者です。短く、具体的に。", schema, check, log=log, effort="low", tool_name="pick", tool_desc="選んだスライドを保存する", max_tokens=2000)
        return [(int(p["i"]), str(p["hook"]).replace("\\n", "\n").strip(), p.get("reason", ""), str(p.get("desc", "")).strip()) for p in o["picks"]][:n]
    except Exception as e:
        log(f"AI 선택 실패 → 점수로 선택 ({str(e)[:120]})"); return None

def _esc(t):
    """AI の文字列を HTML にする: < > & を逃がし、**太字** だけ <b> にする"""
    t = str(t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)

def build_short_spec(long_spec, k, taken=()):
    """AI が返した1本ぶん（slug, title, sub, hook, desc, headers, rows, now, key, speech）から、ショート専用の spec を作る"""
    slug = re.sub(r"[^a-z0-9]", "", str(k.get("slug", "")).lower())[:16] or "k"
    name = f"SHORT_{long_spec['name']}_{slug}"; base, c = name, 2
    while name in taken or os.path.exists(os.path.join(HERE, "specs", name + ".json")): name = f"{base}{c}"; c += 1
    heads = (list(k.get("headers") or []) + ["", ""])[:2]
    now = int(k.get("now") or 0)                                                    # 目立たせる行（1始まり、0=なし）
    NOW = " class='now'"
    trs = "".join(f"<tr{NOW if j == now else ''}><td class='c'>{_esc(r[0])}</td><td class='c'>{_esc(r[1])}</td></tr>" for j, r in enumerate(k["rows"][:4], 1))
    body = f"<table><tr><th class='c'>{_esc(heads[0])}</th><th class='c'>{_esc(heads[1])}</th></tr>{trs}</table>" + (f"<div class='key'>{_esc(k['key'])}</div>" if k.get("key") else "")
    import time
    return {"name": name, "outdir": name.lower(), "label": "【ショート】" + str(k.get("title", "")).strip(), "status": "script",
            "topic": f"ショート動画（専用台本）。本編 {long_spec['name']} のキーワード「{k.get('keyword', '')}」", "created_at": time.strftime("%Y-%m-%d %H:%M"),
            "short_target": long_spec["name"], "short_tags": long_spec.get("short_tags") or "#宅建 #宅建士", "short_badge": long_spec.get("short_badge", ""),
            "usage": {"model": "ai"}, "notes": f"・本編 {long_spec['name']} の内容から AI が作成（数字・事実は本編にあるものだけ）。キーワード: {k.get('keyword', '')}／選んだ理由: {k.get('reason', '')}",
            "youtube": {"title": "", "description": "", "tags": [], "url": ""}, "blog": {"slug": "", "title": "", "excerpt": "", "url": ""},
            "slides": [{"title": str(k.get("title", "")).strip(), "sub": str(k.get("sub", "")).strip(), "short_hook": str(k["hook"]).replace("\\n", "\n").strip(),
                        "short_desc": str(k.get("desc", "")).strip(), "body": body, "speech": str(k["speech"]).strip(), "illust_off": True}]}

def write_dedicated(spec, n, log=print):
    """キーワードごとにショート専用の台本を AI に書かせる。[(spec の dict)] を返す。使えない・失敗なら None"""
    import scriptgen
    if not scriptgen.available(): return None
    rows = []
    for i, s in enumerate(spec["slides"], 1):
        if s.get("photo") and not s.get("body"): continue
        rows.append(f"[{i}] 見出し: {s.get('title') or '（表紙）'}\n本文: {_plain(s.get('body',''))[:500]}\n読み上げ: {(s.get('speech') or '')[:400]}")
    prompt = (f"長い動画（本編）「{spec.get('label','')}」の内容です。この本編に視聴者を連れてくるための YouTube ショート（縦・40〜55秒）を {n} 本、新しく書いてください。\n"
              "本編のスライドを切り出すのではなく、検索・おすすめで止まってもらえる【キーワード1つ】ごとに、ショート専用の1枚と読み上げを書きます。\n"
              "決まり:\n"
              "・数字・固有名詞・事実は、下の本編に書いてあるものだけを使う。新しい数字や推測を足さない。本編で『予想』『目安』とされているものは、ショートでも同じ扱いにする。\n"
              "・1本につきキーワードは1つ。本同士で内容を重ねない。\n"
              "・slug: キーワードを表す英小文字と数字だけ（16字以内）。keyword: 日本語のキーワード。\n"
              "・title: スライドの見出し（16字以内）。sub: 小見出し（14字以内、なければ空）。\n"
              "・hook: 上に大きく出す2行（各行14字以内・改行は \\n）。合格率・点数・日付・金額などの数字があれば必ず1行目に入れる。\n"
              "・headers: 表の見出し2つ。rows: 表の行（2〜4行、各行は [左, 右] の2つ、各セル18字以内）。強調は **太字**。now: いちばん大事な行の番号（1始まり、なければ0）。\n"
              "・key: 表の下に出すひとこと（45字以内、**太字** 可）。\n"
              "・speech: 読み上げ（160〜260字）。1文目で結論か数字を言う。最後の1文は『詳しくは本編でまとめています。』のように本編へつなぐ。強調したい言葉は【】で囲む。記号や英字の羅列は避け、数字は読みやすく。\n"
              "・desc: 概要欄の1行（30〜60字・1文・リンクやタグなし）。reason: そのキーワードを選んだ理由（短く）。\n\n"
              + "\n\n".join(rows))
    item = {"type": "object", "additionalProperties": False, "required": ["slug", "keyword", "title", "sub", "hook", "headers", "rows", "now", "key", "speech", "desc", "reason"],
            "properties": {"slug": {"type": "string"}, "keyword": {"type": "string"}, "title": {"type": "string"}, "sub": {"type": "string"}, "hook": {"type": "string"},
                           "headers": {"type": "array", "items": {"type": "string"}}, "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                           "now": {"type": "integer"}, "key": {"type": "string"}, "speech": {"type": "string"}, "desc": {"type": "string"}, "reason": {"type": "string"}}}
    schema = {"type": "object", "additionalProperties": False, "required": ["shorts"], "properties": {"shorts": {"type": "array", "items": item}}}
    def check(o):
        ks = o.get("shorts") or []
        if not ks: return "shorts が空です"
        for k in ks:
            if not str(k.get("hook", "")).strip(): return "hook が空です"
            rs = k.get("rows") or []
            if not (2 <= len(rs) <= 4) or any(len(r) != 2 for r in rs): return "rows は 2〜4 行、各行は [左, 右] の2つにしてください"
            if any(len(str(c)) > 26 for r in rs for c in r): return "表のセルが長すぎます（18字以内）"
            if not (120 <= len(str(k.get("speech", ""))) <= 320): return "speech は 160〜260 字にしてください"
            if len(str(k.get("desc", "")).strip()) < 15: return "desc が短すぎます（30〜60字の1文）"
        return None
    try:
        o = scriptgen.ask_json(prompt, "あなたはYouTubeショートの構成作家です。事実は与えられた本編の範囲だけ。短く、具体的に。", schema, check, log=log, effort="low",
                               tool_name="write_shorts", tool_desc="ショート専用の台本を保存する", max_tokens=4000)
    except Exception as e:
        log(f"AI 전용 쇼츠 작성 실패 → 장면 선택 방식으로 ({str(e)[:120]})"); return None
    out, taken = [], set()
    for k in (o.get("shorts") or [])[:n]:
        sp = build_short_spec(spec, k, taken); taken.add(sp["name"]); out.append(sp)
    return out or None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--pick", action="store_true", help="以前の方式: 本編のスライドを選んで切り出す"); a = ap.parse_args()
    import shorts
    log = lambda m: print(m, flush=True)
    spec = json.load(open(a.spec, encoding="utf-8"))
    if not a.pick and not spec.get("short_target"):                                 # 既定: キーワードごとの専用ショート（ショート専用 spec 自身には使わない）
        made = write_dedicated(spec, a.n, log)
        if made:
            for sp in made:
                p = os.path.join(HERE, "specs", sp["name"] + ".json")
                json.dump(sp, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                s0 = sp["slides"][0]
                log(f"전용 쇼츠 작성: {sp['name']}  훅: {s0['short_hook'].replace(chr(10), ' / ')}")
                shorts.make(p, 1, s0["short_hook"], log=log)
            return
    picks = ask(spec, a.n, log)
    if not picks:
        picks = [(i, None, "점수") for i in heuristic(spec)[: a.n]]
    for pk in picks:
        i, hook, reason = pk[0], pk[1], pk[2]; desc = pk[3] if len(pk) > 3 else ""
        s = spec["slides"][i - 1]
        hook = hook or s.get("short_hook") or (s.get("title") or "").split("｜")[0]
        log(f"쇼츠 장면 선택: #{i} {s.get('title') or ''}  훅: {hook.replace(chr(10), ' / ')}  ({reason})")
        s["short_hook"] = hook
        if desc: s["short_desc"] = desc
        json.dump(spec, open(a.spec, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        shorts.make(a.spec, i, hook, log=log)

if __name__ == "__main__":
    main()
