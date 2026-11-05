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

def compose_body(spec, s):
    """描画に使う本文 = 本文 + イラスト + 自由配置の要素"""
    import r8_goukaku as G, illust, imgsearch
    log = lambda m: print(m, flush=True)
    body = imgsearch.resolve_tokens(s.get("body", ""), log)   # {{img:会社名 ロゴ}} → 実際のロゴ
    ph = photo_path(s, log)
    if ph:                                                     # 全画面の写真 + (あれば) 見出し・本文
        head = f"<div class='photo-title'>{G.E(s.get('title', ''))}</div>" if s.get("title") else ""
        inner = f"<div class='photo-body'>{body}</div>" if body.strip() else ""
        return f"<img class='photo' src='file://{ph}'>" + head + inner + G.overlays_html(s.get("overlays"))
    body = body if spec.get("illust_off") else illust.inject(s, body)
    return body + G.overlays_html(s.get("overlays"))

def photo_path(s, log=print):
    """photo: "ai:説明" なら実写風に生成、それ以外は検索語（Pexels → Commons → …）。無ければ None"""
    q = (s.get("photo") or "").strip()
    if not q: return None
    import illust, imgsearch
    try:
        if q.lower().startswith("ai:"): return illust.ensure_photo(q[3:])
        if os.path.exists(q): return q
        return imgsearch.resolve(q, "photo", log)
    except Exception as e:
        log(f"사진을 준비하지 못했습니다 ({q}): {str(e)[:160]}"); return None

def setup(spec):
    import r8_goukaku as G, vkit as V
    V.SUB_STYLE = spec.get("sub_style")
    G.MOTION = not spec.get("motion_off")
    G.SLIDES.clear()
    for s in spec["slides"]:
        s["_body"] = compose_body(spec, s)
        photo = "class='photo'" in s["_body"]
        G.SLIDES.append(("" if photo else s.get("title", ""), "" if photo else s.get("sub", ""), s["_body"], s.get("speech", "")))   # 写真の場面は見出しを写真の上に描く
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
            print(f"초안 {i:02d} {total:5.0f}초  {s.get('title') or 'はじめに'}", flush=True)
        else:
            print(f"초안 {i:02d} (변경 없음·재사용)  {s.get('title') or 'はじめに'}", flush=True)
        d = V.dur(seg); segs.append(seg)
        man.append({"i": i, "title": s.get("title") or "はじめに", "key": key, "seg": os.path.basename(seg), "thumb": os.path.basename(thumb), "dur": round(d, 2), "start": round(t, 2)})
        t += d
    final = os.path.join(G.OUT, f"{spec['name']}_draft.mp4")
    V.concat(segs, final, bgm=False)
    json.dump({"name": spec["name"], "video": os.path.basename(final), "total": round(t, 2), "built_at": time.strftime("%Y-%m-%d %H:%M:%S"), "draft": True, "slides": man},
              open(os.path.join(G.OUT, f"{spec['name']}.draft.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("초안 완료:", final, f"{t/60:.1f}분", flush=True)

def set_status(path, status):
    sp = load(path)
    order = ["topic", "script", "draft", "voiced", "uploaded", "blogged"]
    if order.index(status) > order.index(sp.get("status", "script")):
        sp["status"] = status
        tmp = path + ".tmp"; json.dump(sp, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--preview", type=int); ap.add_argument("--preview-all", action="store_true"); ap.add_argument("--explode", type=int); ap.add_argument("--slide-json"); ap.add_argument("--draft", action="store_true")
    ap.add_argument("--illust", type=int, help="絵だけ作る (0=ないもの全部, n=n枚目を作り直す)")
    a = ap.parse_args()
    spec = load(a.spec)
    G = setup(spec)
    if a.illust is not None or a.draft or not (a.preview or a.preview_all or a.explode):  # 絵がないスライドの絵を作る (キーがあるときだけ)
        import illust
        if a.illust: spec = illust.regen(a.spec, a.illust)
        if illust.provider() == "none":
            if a.illust is not None: sys.exit("일러스트를 만들 키가 없습니다 (python3 illust.py --check)")
        elif illust.ensure_spec(spec, a.illust or None, log=lambda m: print(m, flush=True)):
            G = setup(spec)
        if a.illust is not None: return
    if a.draft:
        draft(spec, G); set_status(a.spec, "draft"); return
    if a.preview_all:
        import shutil
        done = 0
        for i, s in enumerate(spec["slides"], 1):
            key = G.slide_key(s.get("title", ""), s.get("sub", ""), s["_body"], s.get("speech", ""))
            dst = os.path.join(G.OUT, f"p_{key}.png")
            if os.path.exists(dst) or os.path.exists(os.path.join(G.OUT, f"c_{key}.png")): continue
            png, h = G.render(s["_body"], s.get("title", ""), s.get("sub", ""), f"pv{i:02d}")
            shutil.copy(png, dst); done += 1
            print(f"미리보기 {i:02d}/{len(spec['slides'])}", flush=True)
        print(f"미리보기 이미지 {done}장 생성", flush=True); return
    if a.explode:
        import illust
        i = a.explode
        s = json.load(open(a.slide_json, encoding="utf-8")) if a.slide_json else spec["slides"][i - 1]
        s = dict(s); s.pop("overlays", None)                        # まず自動レイアウトを描いて、その座標を読む
        body = compose_body(spec, s)
        G.render(body, s.get("title", ""), s.get("sub", ""), f"ex{i:02d}")
        head = f"<h1>{G.E(s.get('title', ''))}<small>{G.E(s.get('sub', ''))}</small></h1>" if s.get("title") else ""
        ovs = G.explode(head, body, G.LAST_SCALE, None if spec.get("illust_off") else illust.path_for(s))
        ovs += [o for o in (json.load(open(a.slide_json, encoding="utf-8")) if a.slide_json else spec["slides"][i - 1]).get("overlays", []) or []]
        new = {k: v for k, v in s.items() if k not in ("_body",)}
        new.update(title="", sub="", body="", overlays=ovs, illust_off=True,
                   _orig={k: s.get(k, "") for k in ("title", "sub", "body", "illust_pos") if k in s or k in ("title", "sub", "body")})
        print(json.dumps(new, ensure_ascii=False)); return
    if a.preview:
        i = a.preview
        s = json.load(open(a.slide_json, encoding="utf-8")) if a.slide_json else spec["slides"][i - 1]
        body = compose_body(spec, s)
        png, h = G.render(body, s.get("title", ""), s.get("sub", ""), f"pv{i:02d}")
        import shutil
        key = G.slide_key(s.get("title", ""), s.get("sub", ""), body, s.get("speech", ""))
        shutil.copy(png, os.path.join(G.OUT, f"p_{key}.png"))
        print(json.dumps({"png": f"p_{key}.png", "page_h": h}))
        return
    G.build(None, name=spec["name"])
    set_status(a.spec, "voiced")

if __name__ == "__main__":
    main()
