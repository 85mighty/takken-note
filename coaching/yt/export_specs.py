# -*- coding: utf-8 -*-
"""既存のスライド型スクリプト (r8_*.py) を specs/*.json に書き出す。一度だけ使う移行用。
  以後は specs/*.json が正 (検収パネルで編集する)。r8_*.py は参考として残す。
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SPECS = os.path.join(HERE, "specs"); os.makedirs(SPECS, exist_ok=True)

# (モジュール, 動画名, 表示名)
MODS = [
    ("r8_goukaku", "R8_goukaku", "合格点予想まとめ 第1弾"),
    ("r8_goukaku2", "R8_goukaku2", "合格点予想まとめ 第2弾"),
    ("r8_keikou", "R8_keikou", "令和7年と8年で何が変わったのか"),
    ("r8_happyou", "R8_happyou", "合格発表の日に何をどう見るか"),
    ("r8_q33", "R8_q33", "割れ問33 正解は1か4か"),
    ("r8_merit", "R8_merit", "宅建に受かったら何が変わる？"),
    ("r8_menjo", "R8_menjo", "5問免除（登録講習）完全ガイド"),
]
CODE = r'''
import json, os, sys
sys.path.insert(0, %r)
import %s
import r8_goukaku as G
print(json.dumps({"outdir": os.path.basename(G.OUT), "slides": [dict(title=t, sub=s, body=b, speech=sp) for t, s, b, sp in G.SLIDES]}, ensure_ascii=False))
'''
for mod, name, label in MODS:
    out = subprocess.run([sys.executable, "-c", CODE % (HERE, mod)], capture_output=True, text=True, cwd=HERE)
    if out.returncode:
        print("NG", mod, out.stderr[-300:]); continue
    d = json.loads(out.stdout.strip().splitlines()[-1])
    spec = {"name": name, "outdir": d["outdir"], "label": label, "slides": d["slides"]}
    p = os.path.join(SPECS, f"{name}.json")
    json.dump(spec, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{name}: {len(d['slides'])}枚 → {os.path.relpath(p, HERE)}")
