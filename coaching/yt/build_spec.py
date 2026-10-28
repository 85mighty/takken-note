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
    G.SLIDES.clear()
    for s in spec["slides"]:
        G.SLIDES.append((s.get("title", ""), s.get("sub", ""), s.get("body", ""), s.get("speech", "")))
    G.OUT = os.path.join(V.OUT, spec["outdir"]); os.makedirs(G.OUT, exist_ok=True)
    return G

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--preview", type=int); ap.add_argument("--slide-json")
    a = ap.parse_args()
    spec = load(a.spec)
    G = setup(spec)
    if a.preview:
        i = a.preview
        s = json.load(open(a.slide_json, encoding="utf-8")) if a.slide_json else spec["slides"][i - 1]
        png, h = G.render(s.get("body", ""), s.get("title", ""), s.get("sub", ""), f"pv{i:02d}")
        print(json.dumps({"png": os.path.basename(png), "page_h": h}))
        return
    G.build(None, name=spec["name"])

if __name__ == "__main__":
    main()
