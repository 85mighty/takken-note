# -*- coding: utf-8 -*-
"""長い動画から「いちばん引きのある1枚」を選んでショートにする。
  python3 short_pick.py specs/R8_xxx.json [--n 2]   … n 本（既定1）作る
  選び方: Claude（API か CLI）に、各スライドの見出し・本文・読み上げを渡して「ショート向きの1枚」と「フック（2行）」を選ばせる。
  Claude が使えなければ、数字・結論・表の多さで点を付けて選ぶ。選んだフックはスライドの short_hook に保存し、shorts.py で縦動画にする。
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

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("--n", type=int, default=1); a = ap.parse_args()
    import shorts
    log = lambda m: print(m, flush=True)
    spec = json.load(open(a.spec, encoding="utf-8"))
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
