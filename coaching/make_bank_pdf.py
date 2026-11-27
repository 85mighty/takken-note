# -*- coding: utf-8 -*-
"""特訓100問 の印刷用 PDF (問題 → 巻末に解答・解説表)。
  python3 coaching/make_bank_pdf.py kenki static/docs/kenki_100.pdf
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import subjects  # noqa: E402

CSS = """
@page { size: A4; margin: 15mm 14mm 14mm; @bottom-center { content: "— " counter(page) " —"; font-size: 10pt; font-family: "Noto Sans CJK JP"; } }
body { font-family: "Noto Sans CJK JP", sans-serif; font-size: 12.5pt; line-height: 1.55; color: #000; margin: 0; }
.cover { text-align: center; padding-top: 20mm; }
.cover h1 { font-size: 24pt; margin-bottom: 8mm; }
.cover p { font-size: 11.5pt; margin: 1mm 0; }
.q { margin: 0 0 7mm; page-break-inside: avoid; }
.qh { font-weight: bold; margin-bottom: 1.5mm; }
.tag { display: inline-block; font-size: 9pt; font-weight: normal; border: 1px solid #000; border-radius: 3mm; padding: 0 2mm; margin: 0 1.5mm; vertical-align: middle; }
.ch { display: flex; margin: 0.8mm 0; }
.ch .n { width: 6mm; flex-shrink: 0; font-weight: bold; }
.ans { page-break-before: always; }
.ans h2 { font-size: 16pt; border-bottom: 2px solid #000; padding-bottom: 1.5mm; }
table { border-collapse: collapse; width: 100%; font-size: 11pt; }
td { border: 1px solid #000; padding: 1.6mm 2mm; vertical-align: top; line-height: 1.45; }
td.no { width: 11mm; text-align: center; white-space: nowrap; }
td.a { width: 9mm; text-align: center; font-weight: bold; font-size: 13pt; }
tr { page-break-inside: avoid; }
.start { page-break-before: always; }
"""


def html(key, items):
    name, q = subjects.name(key), subjects.SUBJECTS[key]["q"]
    n_prac = sum(1 for it in items if "本試験" not in it["tag"] and "模試" not in it["tag"])
    out = [f"<!DOCTYPE html><html lang='ja'><head><meta charset='UTF-8'><style>{CSS}</style></head><body>"]
    out.append(f"<div class='cover'><h1>{name}　{q.replace('・', '・問')}　特訓100問</h1>"
               f"<p>問1〜{n_prac}：練習問題（暗記ノートの全章から出題）</p>"
               f"<p>問{n_prac + 1}〜100：本試験の{q}（改題を含む）</p>"
               f"<p>法令は令和8年4月1日現在（令和7年4月施行の改正を反映）。4点セットで解き、解答・解説は巻末。</p></div>")
    out.append("<div class='start'>")
    for it in items:
        tag = it["tag"]
        out.append(f"<div class='q'><div class='qh'>【問 {it['n']:>2}】<span class='tag'>{tag}</span>{it['stem']}</div>")
        for s in it.get("subs") or []:
            out.append(f"<div>{s}</div>")
        for i, c in enumerate(it["choices"], 1):
            out.append(f"<div class='ch'><span class='n'>{i}</span><span>{c}</span></div>")
        out.append("</div>")
    out.append("</div><div class='ans'><h2>解答・解説</h2><table>")
    for it in items:
        a = it["answer"]
        a = "・".join(map(str, a)) if isinstance(a, list) else str(a)
        out.append(f"<tr><td class='no'>問{it['n']}</td><td class='a'>{a}</td><td>{it.get('exp', '')}</td></tr>")
    out.append("</table></div></body></html>")
    return "\n".join(out)


if __name__ == "__main__":
    from weasyprint import HTML
    key, outpath = sys.argv[1], sys.argv[2]
    items = json.load(open(os.path.join(HERE, f"{key}_100.json"), encoding="utf-8"))
    HTML(string=html(key, items)).write_pdf(outpath)
    print("ok", outpath)
