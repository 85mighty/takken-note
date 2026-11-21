#!/usr/bin/env python3
"""宅建ベンチマーク分析: out/videos_*.json → テーマ別・タイトルの型別・長さ別・投稿月別の「伸び方」
  チャンネルの大きさが違うので、再生数は「そのチャンネルの中央値に対して何倍か」(相対スコア) で比べる。
  投稿日が取れていれば「1日あたり再生数」で比べ、古い動画ほど有利になる偏りを抑える。
  出力: out/summary.md, out/summary.html（検収パネル /studio/bench で表示）, out/*.csv
"""
import csv, html, json, re, statistics, time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

# テーマ（上から順に最初に当たったもの。形式 → 科目 の順）
TOPICS = [
    ("合格点・合格発表",        r"合格点|合格ライン|合格発表|ボーダー|合格基準|何点"),
    ("解答速報・本試験解説",     r"解答速報|本試験|速報|問\d+|解答解説"),
    ("直前対策・予想",          r"直前|予想問題|予想|ヤマ|出る|狙われ|当日|前日|ラスト|最後の|残り\d"),
    ("勉強法・スケジュール",     r"勉強法|独学|スケジュール|勉強時間|計画|テキスト|参考書|おすすめ|何から|始め方|初学者|初心者|合格する方法|落ちる人|受かる人|点数を?上げ"),
    ("一問一答・聞き流し・暗記",  r"一問一答|聞き流し|[〇○◯]×|暗記|ゴロ|語呂|覚え方|作業用|睡眠|寝ながら"),
    ("過去問演習",              r"過去問"),
    ("宅建業法",                r"業法|重要事項|重説|35条|37条|報酬|クーリング|媒介|営業保証金|保証協会|免許|宅建士証|8種制限|手付|広告"),
    ("権利関係・民法",           r"民法|権利関係|借地|借家|区分所有|相続|抵当|代理|時効|意思表示|契約|賃貸借|不動産登記|物権|債権|共有|遺留分|保証"),
    ("法令上の制限",             r"法令上の制限|都市計画|建築基準|用途地域|建ぺい|建蔽|容積|農地法|国土利用|盛土|宅地造成|区画整理|開発許可"),
    ("税・その他（免除科目）",    r"税|免除科目|5問免除|統計|景表|景品表示|住宅金融|鑑定評価|地価公示|土地の形質|建物の構造"),
    ("法改正",                  r"改正|新制度|新法"),
    ("キャリア・お金",           r"年収|転職|就職|手当|仕事|ダブルライセンス|行政書士|賃貸不動産経営管理士|管理業務主任者|FP|稼"),
    ("ライブ配信",              r"ライブ|生配信|LIVE|Live"),
]
PATTERNS = [
    ("先頭が【】",                 r"^【"),
    ("末尾に【補足タグ】",           r"【[^】]+】\s*$"),
    ("年度を明示（2026/令和8）",     r"20\d\d|令和\s?\d"),
    ("点数を明示（○点）",           r"\d+点"),
    ("数字リスト（○選/○つ）",       r"\d+選|\d+つ"),
    ("時間を明示（○分/○時間）",      r"\d+分|\d+時間"),
    ("疑問形（？）",                r"[？?]"),
    ("感嘆（！）",                  r"[！!]"),
    ("不安・警告（落ちる/注意/知らないと）", r"落ちる|落ちた|危険|注意|ひっかけ|引っかけ|罠|ヤバ|やば|知らないと|損"),
    ("断言（絶対/必ず/完全）",        r"絶対|必ず|確実|完全|最強"),
    ("初心者向け",                  r"初心者|初学者|ゼロから|超入門|基礎|わかりやすく|分かりやすく|やさしく"),
    ("まとめ・総集編",               r"まとめ|総まとめ|総集編|全部|すべて|全て|全\d+問"),
    ("一問一答・聞き流し",            r"一問一答|聞き流し"),
]
DUR = [(0, 5 * 60, "〜5分"), (5 * 60, 15 * 60, "5〜15分"), (15 * 60, 30 * 60, "15〜30分"), (30 * 60, 60 * 60, "30〜60分"), (60 * 60, 10 ** 9, "60分〜")]

def topic_of(t):
    for name, pat in TOPICS:
        if re.search(pat, t): return name
    return "その他"

def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None

def load():
    chans = []
    for p in sorted(OUT.glob("videos_*.json")):
        d = json.load(open(p, encoding="utf-8"))
        vids = [v for v in d["videos"] if v.get("view_count") is not None]
        if not vids: continue
        today = date.today()
        for v in vids:
            ud = v.get("upload_date")
            if ud and re.fullmatch(r"\d{8}", str(ud)):
                dd = date(int(ud[:4]), int(ud[4:6]), int(ud[6:]))
                v["days"] = max(7, (today - dd).days); v["month"] = dd.month; v["ym"] = f"{dd.year}-{dd.month:02d}"
                v["vpd"] = v["view_count"] / v["days"]
            else:
                v["days"] = v["month"] = v["ym"] = v["vpd"] = None
        dated = sum(1 for v in vids if v["vpd"] is not None) / len(vids)
        use_vpd = dated >= 0.8
        base = med([v["vpd"] for v in vids]) if use_vpd else med([v["view_count"] for v in vids])
        for v in vids:
            x = v["vpd"] if use_vpd else v["view_count"]
            v["rel"] = (x / base) if (x is not None and base) else None
            v["topic"] = topic_of(v["title"]); v["channel"] = d["name"]; v["self"] = d.get("self", False)
        chans.append({"name": d["name"], "url": d.get("url"), "self": d.get("self", False), "n": len(vids), "median": med([v["view_count"] for v in vids]),
                      "max": max(v["view_count"] for v in vids), "metric": "1日あたり再生数" if use_vpd else "累計再生数", "dated": dated,
                      "collected_at": d.get("collected_at"), "videos": vids})
    return chans

def analyze(chans):
    bench = [v for c in chans if not c["self"] for v in c["videos"] if v["rel"] is not None]
    selfv = [v for c in chans if c["self"] for v in c["videos"] if v["rel"] is not None]
    # テーマ
    topics = []
    for name in [t for t, _ in TOPICS] + ["その他"]:
        vs = [v for v in bench if v["topic"] == name]
        if not vs: continue
        hits = sum(1 for v in vs if v["rel"] >= 2)
        topics.append({"topic": name, "n": len(vs), "share": len(vs) / len(bench), "rel_med": med([v["rel"] for v in vs]),
                       "hit_rate": hits / len(vs), "views_med": med([v["view_count"] for v in vs]),
                       "chans": len({v["channel"] for v in vs}), "self_n": sum(1 for v in selfv if v["topic"] == name),
                       "self_rel": med([v["rel"] for v in selfv if v["topic"] == name])})
    for t in topics: t["score"] = (t["rel_med"] or 0) * (0.5 + t["hit_rate"]) * min(1.0, t["n"] / 10)
    topics.sort(key=lambda t: t["score"], reverse=True)
    # タイトルの型
    pats = []
    for name, pat in PATTERNS:
        w = [v["rel"] for v in bench if re.search(pat, v["title"])]
        wo = [v["rel"] for v in bench if not re.search(pat, v["title"])]
        if len(w) < 5 or not wo: continue
        pats.append({"pattern": name, "n": len(w), "share": len(w) / len(bench), "with": med(w), "without": med(wo), "lift": med(w) / med(wo)})
    pats.sort(key=lambda p: p["lift"], reverse=True)
    # 長さ
    durs = []
    for lo, hi, lab in DUR:
        vs = [v["rel"] for v in bench if v.get("duration") and lo <= v["duration"] < hi]
        if vs: durs.append({"len": lab, "n": len(vs), "rel_med": med(vs), "hit_rate": sum(1 for x in vs if x >= 2) / len(vs)})
    # 投稿月
    months = []
    for m in range(1, 13):
        vs = [v for v in bench if v["month"] == m]
        if not vs: continue
        tc = Counter(v["topic"] for v in vs if v["rel"] >= 2)
        months.append({"month": m, "n": len(vs), "rel_med": med([v["rel"] for v in vs]), "hit_topics": "、".join(f"{k}({n})" for k, n in tc.most_common(3))})
    top = sorted(bench, key=lambda v: v["rel"], reverse=True)[:40]
    return dict(bench_n=len(bench), self_n=len(selfv), topics=topics, pats=pats, durs=durs, months=months, top=top,
                self_top=sorted(selfv, key=lambda v: v["rel"], reverse=True)[:15])

def f1(x, nd=2): return "—" if x is None else f"{x:.{nd}f}"
def pct(x): return "—" if x is None else f"{x*100:.0f}%"
def mmss(s): return "—" if not s else f"{int(s)//60}:{int(s)%60:02d}"

def recommend(R):
    rec = []
    good = [t for t in R["topics"] if (t["rel_med"] or 0) >= 1.1 and t["n"] >= 8]
    if good: rec.append("**伸びやすいテーマ**: " + "、".join(f"{t['topic']}（中央値 {f1(t['rel_med'])}倍・2倍超 {pct(t['hit_rate'])}）" for t in good[:4]))
    lift = [p for p in R["pats"] if p["lift"] >= 1.15]
    if lift: rec.append("**効くタイトルの型**: " + "、".join(f"{p['pattern']}（{f1(p['lift'])}倍）" for p in lift[:5]))
    bad = [p for p in R["pats"] if p["lift"] <= 0.85]
    if bad: rec.append("**逆効果になりやすい型**: " + "、".join(f"{p['pattern']}（{f1(p['lift'])}倍）" for p in bad[:4]))
    if R["durs"]:
        b = max(R["durs"], key=lambda d: d["rel_med"] or 0); rec.append(f"**長さ**: {b['len']} が最も伸びやすい（中央値 {f1(b['rel_med'])}倍）")
    gap = [t for t in R["topics"] if (t["rel_med"] or 0) >= 1.1 and t["self_n"] == 0]
    if gap: rec.append("**自チャンネルでまだ出していない伸びるテーマ**: " + "、".join(t["topic"] for t in gap[:4]))
    return rec

def write(chans, R):
    ts = time.strftime("%Y-%m-%d %H:%M")
    # CSV
    with open(OUT / "videos_all.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["channel", "id", "upload_date", "duration", "views", "rel", "topic", "title"])
        for c in chans:
            for v in c["videos"]: w.writerow([c["name"], v["id"], v.get("upload_date"), v.get("duration"), v["view_count"], f1(v["rel"], 3), v["topic"], v["title"]])
    with open(OUT / "topic_ranking.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["topic", "n", "share", "rel_median", "hit_rate", "views_median", "channels", "self_n", "score"])
        for t in R["topics"]: w.writerow([t["topic"], t["n"], f1(t["share"], 3), f1(t["rel_med"], 3), f1(t["hit_rate"], 3), t["views_med"], t["chans"], t["self_n"], f1(t["score"], 3)])
    with open(OUT / "title_patterns.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["pattern", "n", "share", "rel_with", "rel_without", "lift"])
        for p in R["pats"]: w.writerow([p["pattern"], p["n"], f1(p["share"], 3), f1(p["with"], 3), f1(p["without"], 3), f1(p["lift"], 3)])
    # Markdown
    L = [f"# 宅建 YouTube ベンチマーク分析（{ts}）", "",
         f"- 対象: ベンチマーク {sum(1 for c in chans if not c['self'])}チャンネル・{R['bench_n']}本 ／ 自チャンネル {R['self_n']}本",
         "- 相対スコア＝その動画の再生数 ÷ 同じチャンネルの中央値（投稿日が取れたチャンネルは1日あたり再生数で計算）。1.0＝そのチャンネルの普通、2.0以上＝ヒット", ""]
    L += ["## まとめ（次の動画選びに使う）", ""] + [f"- {r}" for r in recommend(R)] + [""]
    L += ["## チャンネル一覧", "", "| チャンネル | 本数 | 再生数中央値 | 最大 | 比較の指標 | 収集日 |", "|---|---|---|---|---|---|"]
    for c in chans: L.append(f"| {c['name']}{'（自分）' if c['self'] else ''} | {c['n']} | {c['median']:,.0f} | {c['max']:,} | {c['metric']} | {c['collected_at']} |")
    L += ["", "## テーマ別ランキング", "", "| # | テーマ | 本数 | 構成比 | 相対スコア中央値 | 2倍超の割合 | 再生数中央値 | 出しているチャンネル数 | 自分の本数 |", "|---|---|---|---|---|---|---|---|---|"]
    for i, t in enumerate(R["topics"], 1):
        L.append(f"| {i} | {t['topic']} | {t['n']} | {pct(t['share'])} | {f1(t['rel_med'])} | {pct(t['hit_rate'])} | {t['views_med']:,.0f} | {t['chans']} | {t['self_n']} |")
    L += ["", "## タイトルの型の効き目（ある/なしの相対スコア中央値）", "", "| 型 | 使用本数 | 比率 | あり | なし | 効き目(倍) |", "|---|---|---|---|---|---|"]
    for p in R["pats"]: L.append(f"| {p['pattern']} | {p['n']} | {pct(p['share'])} | {f1(p['with'])} | {f1(p['without'])} | {f1(p['lift'])} |")
    L += ["", "## 動画の長さ", "", "| 長さ | 本数 | 相対スコア中央値 | 2倍超の割合 |", "|---|---|---|---|"]
    for d in R["durs"]: L.append(f"| {d['len']} | {d['n']} | {f1(d['rel_med'])} | {pct(d['hit_rate'])} |")
    if R["months"]:
        L += ["", "## 投稿月（いつ何が伸びるか）", "", "| 月 | 本数 | 相対スコア中央値 | その月にヒットしたテーマ |", "|---|---|---|---|"]
        for m in R["months"]: L.append(f"| {m['month']}月 | {m['n']} | {f1(m['rel_med'])} | {m['hit_topics'] or '—'} |")
    L += ["", "## 相対スコア TOP40（各チャンネルの中で特に伸びた動画）", "", "| 倍 | 再生数 | 長さ | チャンネル | テーマ | タイトル |", "|---|---|---|---|---|---|"]
    for v in R["top"]: L.append(f"| {f1(v['rel'], 1)} | {v['view_count']:,} | {mmss(v.get('duration'))} | {v['channel']} | {v['topic']} | {v['title']} |")
    if R["self_top"]:
        L += ["", "## 自チャンネル（NIPPONリアル）で伸びた動画", "", "| 倍 | 再生数 | テーマ | タイトル |", "|---|---|---|---|"]
        for v in R["self_top"]: L.append(f"| {f1(v['rel'], 1)} | {v['view_count']:,} | {v['topic']} | {v['title']} |")
    md = "\n".join(L) + "\n"
    (OUT / "summary.md").write_text(md, encoding="utf-8")
    (OUT / "summary.html").write_text(to_html(md), encoding="utf-8")

def to_html(md):
    out, tbl = [], []
    def flush():
        if not tbl: return
        rows = [r for r in tbl if not re.fullmatch(r"\|[-| ]+\|", r)]
        cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
        out.append("<div class='tw'><table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells[0]) + "</tr></thead><tbody>"
                   + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:]) + "</tbody></table></div>")
        tbl.clear()
    def inline(s): return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(s))
    for line in md.splitlines():
        if line.startswith("|"): tbl.append(line); continue
        flush()
        if line.startswith("# "): out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "): out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("- "): out.append(f"<li>{inline(line[2:])}</li>")
        elif line.strip(): out.append(f"<p>{inline(line)}</p>")
    flush()
    body = "\n".join(out).replace("</h2>\n<li>", "</h2>\n<ul><li>")
    body = re.sub(r"(<li>.*?</li>)(?!\n<li>)", r"\1</ul>", body, flags=re.S) if "<ul>" in body else body
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>宅建ベンチマーク</title><style>
body{{font-family:"Noto Sans JP","Hiragino Sans",sans-serif;margin:0;background:#f5f6f8;color:#111}}
.wrap{{max-width:1200px;margin:0 auto;padding:16px}}
h1{{font-size:22px;color:#1a3d7c}} h2{{font-size:18px;border-left:6px solid #1a3d7c;padding-left:10px;margin-top:28px}}
li{{margin:6px 0 6px 18px;line-height:1.6}} p{{line-height:1.6}}
.tw{{overflow-x:auto;background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border-bottom:1px solid #e3e6ec;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#1a3d7c;color:#fff;position:sticky;top:0;white-space:nowrap}} tr:hover td{{background:#fffbe6}}
a.back{{display:inline-block;margin-bottom:8px}}
</style></head><body><div class="wrap"><a class="back" href="/studio/">← スタジオへ戻る</a>
{body}</div></body></html>"""

if __name__ == "__main__":
    chans = load()
    if not chans: raise SystemExit("out/videos_*.json がありません。先に collect.py を実行してください。")
    R = analyze(chans); write(chans, R)
    print(f"分析: {len(chans)}チャンネル・ベンチマーク{R['bench_n']}本 → {OUT/'summary.html'}")
    for r in recommend(R): print(" -", re.sub(r"\*\*", "", r))
