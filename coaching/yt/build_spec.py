# -*- coding: utf-8 -*-
"""specs/<name>.json (スライド型動画の定義) から動画を作る。検収パネル (/studio) からも呼ばれる。
  python3 build_spec.py specs/R8_menjo.json               … 書き出し (変わったスライドだけ作り直し)
  python3 build_spec.py specs/R8_menjo.json --preview 3   … 3枚目の画像だけ作る (音声なし・数秒)
      --slide-json path  … 保存前の編集中スライド (title/sub/body/speech) を使ってプレビュー

spec の形:
  {"name": "R8_menjo", "outdir": "menjo", "label": "表示名",
   "slides": [{"title": "...", "sub": "", "body": "<html>", "speech": "読み上げ"}, ...]}
"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
SPECS = os.path.join(HERE, "specs")

def load(path):
    return json.load(open(path, encoding="utf-8"))

def setup(spec):
    import r8_goukaku as G, vkit as V
    import illust
    V.SUB_STYLE = spec.get("sub_style")
    G.SLIDES.clear()
    for s in spec["slides"]:
        s["_body"] = s.get("body", "") if spec.get("illust_off") else illust.inject(s, s.get("body", ""))
        G.SLIDES.append((s.get("title", ""), s.get("sub", ""), s["_body"], s.get("speech", "")))
    G.OUT = os.path.join(V.OUT, spec["outdir"]); os.makedirs(G.OUT, exist_ok=True)
    return G

CPS = 4.3   # 読み上げ速度の目安（字/秒）。下書きの字幕の長さに使う

def draft(spec, G):
    """音声なしの下書き動画: スライド画像＋映画風字幕（読み上げ文を文字数で時間配分）。確認用なので数十秒で作れる"""
    import shutil, subprocess, time
    import vkit as V
    from r8_goukaku import H, scroll_expr
    segs, man, t = [], [], 0.0
    for i, s in enumerate(spec["slides"], 1):
        key = G.slide_key(s.get("title", ""), s.get("sub", ""), s["_body"], s.get("speech", ""))
        seg = os.path.join(G.OUT, f"d_{key}.mp4"); thumb = os.path.join(G.OUT, f"c_{key}.png")
        sents = V.split_sentences(s.get("speech", "")) or ["（読み上げなし）"]
        starts, cur = {}, 0.6
        for k, x in enumerate(sents):
            starts[f"s{k}"] = cur; cur += max(1.2, len(x) / CPS) + 0.35
        total = cur + 1.0
        if not os.path.exists(seg):
            png, h = G.render(s["_body"], s.get("title", ""), s.get("sub", ""), f"d{i:02d}")
            mp3 = os.path.join(G.OUT, f"d{i:02d}_silent.m4a")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{total:.2f}", "-c:a", "aac", mp3], check=True)
            pts = [(2.0, 0), (total - 2.0, h - H)] if h > H else []
            tmp = seg + ".part.mp4"
            V.encode_subtitled(png, mp3, scroll_expr(pts, max(0, h - H), total), total, sents, starts, tmp, G.OUT, f"d{i:02d}")
            os.replace(tmp, seg)
            if not os.path.exists(thumb): shutil.copy(png, thumb)
            print(f"draft {i:02d} {total:5.0f}s  {s.get('title') or 'はじめに'}", flush=True)
        else:
            print(f"draft {i:02d} (変更なし・再利用)  {s.get('title') or 'はじめに'}", flush=True)
        d = V.dur(seg); segs.append(seg)
        man.append({"i": i, "title": s.get("title") or "はじめに", "key": key, "seg": os.path.basename(seg), "thumb": os.path.basename(thumb), "dur": round(d, 2), "start": round(t, 2)})
        t += d
    final = os.path.join(G.OUT, f"{spec['name']}_draft.mp4")
    V.concat(segs, final, bgm=False)
    json.dump({"name": spec["name"], "video": os.path.basename(final), "total": round(t, 2), "built_at": time.strftime("%Y-%m-%d %H:%M:%S"), "draft": True, "slides": man},
              open(os.path.join(G.OUT, f"{spec['name']}.draft.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("下書き完了:", final, f"{t/60:.1f}分", flush=True)

def set_status(path, status):
    sp = load(path)
    order = ["topic", "script", "draft", "voiced", "uploaded", "blogged"]
    if order.index(status) > order.index(sp.get("status", "script")):
        sp["status"] = status
        tmp = path + ".tmp"; json.dump(sp, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--preview", type=int); ap.add_argument("--slide-json"); ap.add_argument("--draft", action="store_true")
    ap.add_argument("--illust", type=int, help="絵だけ作る (0=ないもの全部, n=n枚目を作り直す)")
    a = ap.parse_args()
    spec = load(a.spec)
    G = setup(spec)
    if a.illust is not None or a.draft or not a.preview:  # 絵がないスライドの絵を作る (キーがあるときだけ)
        import illust
        if a.illust: spec = illust.regen(a.spec, a.illust)
        if illust.provider() == "none":
            if a.illust is not None: sys.exit("イラストを作るキーがありません (python3 illust.py --check)")
        elif illust.ensure_spec(spec, a.illust or None, log=lambda m: print(m, flush=True)):
            G = setup(spec)
        if a.illust is not None: return
    if a.draft:
        draft(spec, G); set_status(a.spec, "draft"); return
    if a.preview:
        i = a.preview
        s = json.load(open(a.slide_json, encoding="utf-8")) if a.slide_json else spec["slides"][i - 1]
        import illust
        body = s.get("body", "") if spec.get("illust_off") else illust.inject(s, s.get("body", ""))
        png, h = G.render(body, s.get("title", ""), s.get("sub", ""), f"pv{i:02d}")
        print(json.dumps({"png": os.path.basename(png), "page_h": h}))
        return
    G.build(None, name=spec["name"])
    set_status(a.spec, "voiced")

if __name__ == "__main__":
    main()
