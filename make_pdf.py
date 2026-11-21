"""オ답ノートPDF生成
python3 make_pdf.py takken_db.json out.pdf [--year R7] [--category 権利関係] [--min-wrong 1]
"""
import json, sys, argparse, html
from collections import Counter, defaultdict
from datetime import date
from weasyprint import HTML

ap = argparse.ArgumentParser()
ap.add_argument("db"); ap.add_argument("out")
ap.add_argument("--year", default=None)
ap.add_argument("--category", default=None)
ap.add_argument("--min-wrong", type=int, default=1)
ap.add_argument("--title", default=None)
a = ap.parse_args()

db = json.load(open(a.db, encoding="utf-8"))
cats = db["meta"]["categories"]
qs = db["questions"]

sel = [q for q in qs
       if len(q["wrong_dates"]) >= a.min_wrong
       and (a.year is None or q["year"] == a.year)
       and (a.category is None or q["category"] == a.category)]

title = a.title or f"宅建士 誤答ノート {a.year or '全年度'}{(' ' + a.category) if a.category else ''}"

# ---- 集計 ----
tot = Counter((q["year"], q["category"]) for q in qs if (a.year is None or q["year"] == a.year))
wr = Counter((q["year"], q["category"]) for q in sel)
years = sorted({q["year"] for q in qs if (a.year is None or q["year"] == a.year)})

sum_rows = ""
for y in years:
    cells = ""
    tw = tt = 0
    for c in cats:
        t = tot[(y, c)]; w = wr[(y, c)]
        tw += w; tt += t
        cells += f"<td>{t - w}/{t}<br><span class='miss'>誤{w}</span></td>"
    sum_rows += f"<tr><th>{y}</th>{cells}<td class='tot'>{tt - tw}/{tt}</td></tr>"

sub_cnt = Counter(q["subtopic"] for q in sel)
sub_rows = "".join(f"<tr><td>{html.escape(k)}</td><td>{v}</td></tr>"
                   for k, v in sub_cnt.most_common() if v >= 1)

# ---- 問題 ----
def esc(s): return html.escape(s)

blocks = ""
by_cat = defaultdict(list)
for q in sel: by_cat[q["category"]].append(q)
for c in cats:
    if c not in by_cat: continue
    blocks += f"<h2>{c}</h2>"
    for q in sorted(by_cat[c], key=lambda q: (q["year"], q["number"])):
        subs = "".join(f"<div class='sub'>{esc(s)}</div>" for s in q["subs"])
        chs = "".join(f"<div class='ch'><span class='n'>{i+1}</span>{esc(ch)}</div>"
                      for i, ch in enumerate(q["choices"]))
        nwrong = len(q["wrong_dates"])
        blocks += f"""
<div class='q'>
  <div class='qh'><span class='tag'>{q['year']} 問{q['number']}</span>
    <span class='topic'>{esc(q['subtopic'])}</span>
    <span class='cnt'>誤答 {nwrong}回</span></div>
  <div class='stem'>{esc(q['stem'])}</div>
  {subs}
  <div class='choices'>{chs}</div>
  <div class='ans'>正解　<b>{"・".join(map(str, q['answer'])) if isinstance(q['answer'], list) else q['answer']}</b>
    <span class='reason'>誤答理由：{esc(q.get('error_reason') or '＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿')}</span></div>
</div>"""

css = """
@page { size: A4; margin: 16mm 14mm; @bottom-center { content: counter(page) " / " counter(pages); font-size: 10pt; color:#888; } }
body { font-family: 'Noto Sans CJK JP', sans-serif; font-size: 12.5pt; line-height: 1.75; color:#222; }
h1 { font-size: 20pt; margin: 0 0 4mm 0; border-bottom: 3px solid #1a4f8a; padding-bottom: 2mm; }
h2 { font-size: 16pt; color:#fff; background:#1a4f8a; padding: 2mm 4mm; margin: 8mm 0 4mm 0; page-break-after: avoid; }
.meta { color:#666; font-size: 10.5pt; margin-bottom: 5mm; }
table { border-collapse: collapse; margin-bottom: 6mm; font-size: 11.5pt; }
th, td { border: 1px solid #bbb; padding: 1.5mm 3mm; text-align:center; }
th { background:#eef3f9; }
td.tot { font-weight:bold; background:#fff8e1; }
.miss { color:#c62828; font-size: 9.5pt; }
h3 { font-size: 13pt; margin: 6mm 0 2mm 0; }
.q { border: 1.5px solid #cfd8e3; border-radius: 3mm; padding: 4mm 5mm; margin-bottom: 6mm; page-break-inside: avoid; }
.qh { margin-bottom: 2mm; }
.tag { background:#1a4f8a; color:#fff; padding: 0.5mm 3mm; border-radius: 2mm; font-weight:bold; margin-right: 3mm; }
.topic { color:#1a4f8a; font-weight:bold; }
.cnt { float:right; color:#c62828; font-size: 10.5pt; }
.stem { margin-bottom: 2mm; }
.sub { padding-left: 6mm; text-indent: -6mm; margin: 1mm 0 1mm 6mm; }
.choices { margin-top: 2mm; }
.ch { padding-left: 8mm; text-indent: -8mm; margin: 1.2mm 0; }
.ch .n { display:inline-block; width: 6mm; text-indent:0; font-weight:bold; color:#1a4f8a; margin-right: 2mm; }
.ans { margin-top: 3mm; border-top: 1px dashed #aaa; padding-top: 2mm; color:#c62828; }
.ans b { font-size: 15pt; }
.reason { color:#555; margin-left: 8mm; font-size: 11pt; }
.sum2 td:first-child { text-align:left; }
"""

doc = f"""<html><head><meta charset='utf-8'><style>{css}</style></head><body>
<h1>{esc(title)}</h1>
<div class='meta'>対象：{len(sel)}問（誤答{a.min_wrong}回以上）　作成：{date.today().isoformat()}</div>
<h3>分野別 正答数</h3>
<table><tr><th>年度</th>{''.join(f'<th>{c}</th>' for c in cats)}<th>合計</th></tr>{sum_rows}</table>
<h3>細目別 誤答数</h3>
<table class='sum2'><tr><th>細目</th><th>誤答</th></tr>{sub_rows}</table>
{blocks}
</body></html>"""

HTML(string=doc).write_pdf(a.out)
print("wrote", a.out, len(sel), "questions")
