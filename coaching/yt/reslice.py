# -*- coding: utf-8 -*-
"""長いスライドを AI で細かく分ける（読み上げ文は一字も変えず、区切りと画面だけ作り直す → 変わったスライドだけ音声を作り直す）。
  python3 reslice.py specs/R8_xxx.json --sec 25          … 読み上げが 25秒 を超えるスライドを全部分ける
  python3 reslice.py specs/R8_xxx.json --slide 4         … 4枚目だけ分ける
"""
import argparse, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
CPS = 4.3

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["parts"], "properties": {
    "parts": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["title", "sub", "body", "speech", "illust"],
              "properties": {"title": {"type": "string"}, "sub": {"type": "string"}, "body": {"type": "string"}, "speech": {"type": "string"}, "illust": {"type": "string"}}}}}}

def _norm(t): return re.sub(r"\s+", "", t or "")

def split_one(s, sec, log=print):
    import scriptgen
    n = max(2, round(len(s.get("speech", "")) / CPS / sec + 0.5))
    prompt = (f"次のスライド1枚を、読み上げ (speech) の切れ目で {n} 枚前後に分けてください。1枚の読み上げは約{sec}秒（{int(sec*CPS)}字）以内。\n"
              f"【絶対条件】全パーツの speech をつなげると元の speech と一字一句同じになること（言い換え・追加・削除・省略は禁止。句点「。」の位置で切る）。\n"
              f"各パーツの body は、その部分の読み上げに対応する内容だけを元の body の書き方（同じ HTML クラス）で作り直す。title は元の見出しを活かし、2枚目以降は「見出し②」のように続き番号をつける。\n\n"
              f"{scriptgen.SLIDE_GUIDE}\n\n■ 元のスライド\n{json.dumps({k: s.get(k, '') for k in ('title', 'sub', 'body', 'speech', 'illust')}, ensure_ascii=False)}")
    orig = _norm(s.get("speech", ""))
    def check(o):
        ps = o.get("parts") if isinstance(o, dict) else None
        if not isinstance(ps, list) or len(ps) < 2: return "parts が2枚未満です"
        if any(not isinstance(p, dict) or not all(isinstance(p.get(k), str) for k in ("title", "sub", "body", "speech", "illust")) for p in ps): return "項目が欠けています"
        if _norm("".join(p["speech"] for p in ps)) != orig: return "speech をつなげても元と一致しません（言い換えず、切るだけにしてください）"
        return None
    return scriptgen.ask_json(prompt, "あなたは宅建 YouTube の台本編集者です。", SCHEMA, check, log=log, effort="medium", tool_name="save_parts",
                              tool_desc="分けたスライドを保存する")["parts"]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("--sec", type=float, default=25); ap.add_argument("--slide", type=int)
    a = ap.parse_args()
    sp = json.load(open(a.spec, encoding="utf-8")); log = lambda m: print(m, flush=True)
    out, done = [], 0
    for i, s in enumerate(sp["slides"], 1):
        secs = len(s.get("speech", "")) / CPS
        if (a.slide and i != a.slide) or (not a.slide and secs <= a.sec * 1.3):
            out.append(s); continue
        log(f"슬라이드 {i} ({secs:.0f}초) 나누는 중…")
        try:
            parts = split_one(s, a.sec, log)
        except Exception as e:
            log(f"  ✗ {str(e)[:200]}"); out.append(s); continue
        for p in parts:
            q = {k: v for k, v in s.items() if k not in ("title", "sub", "body", "speech", "illust", "illust_seed", "overlays", "_body")}
            q.update(p); out.append(q)
        log(f"  → {len(parts)}장으로"); done += 1
    sp["slides"] = out
    for s in sp["slides"]: s.pop("_body", None)
    with open(a.spec + ".tmp", "w", encoding="utf-8") as f: json.dump(sp, f, ensure_ascii=False, indent=1)
    os.replace(a.spec + ".tmp", a.spec)
    log(f"완료: {done}장을 나눠 전체 {len(out)}장")

if __name__ == "__main__":
    main()
