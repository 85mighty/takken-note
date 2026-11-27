# -*- coding: utf-8 -*-
"""【速報】令和8年度 宅建 合格点は◯点 (11/25 当日用テンプレート)
  1) sokuhou_r8.json に発表の数字を入れる (score, score_menjo, pass_rate, passers, examinees, q33, answers)
  2) python3 r8_sokuhou.py            … 動画を作る (変更のないスライドは再利用)
     python3 r8_sokuhou.py --preview  … 音声なしでスライド画像だけ作る (レイアウト確認用)
  3) out/sokuhou/youtube.txt に タイトル・概要欄・タグ を書き出す
"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import r8_goukaku as G
import vkit as V
from r8_q import Q

G.SLIDES.clear()
G.OUT = os.path.join(V.OUT, "sokuhou"); os.makedirs(G.OUT, exist_ok=True)
slide = G.slide

D = json.load(open(os.environ.get("SOKUHOU_JSON", os.path.join(HERE, "sokuhou_r8.json")), encoding="utf-8"))
def v(key, fmt="{}", blank="◯◯"):
    x = D.get(key)
    return blank if x is None else fmt.format(x)
SC = D.get("score"); MJ = D.get("score_menjo")
if MJ is None and SC is not None: MJ = SC - 5
RATE = D.get("pass_rate"); PASSERS = D.get("passers"); EXAM = D.get("examinees"); Q33 = D.get("q33")
ANS = {int(k): int(x) for k, x in (D.get("answers") or {}).items()}
if Q33 is None and 33 in ANS: Q33 = ANS[33]
s_sc = "◯◯" if SC is None else str(SC)
s_mj = "◯◯" if MJ is None else str(MJ)
s_rate = "◯◯" if RATE is None else f"{RATE}"
s_pass = "◯◯" if PASSERS is None else f"{PASSERS:,}"
s_exam = "◯◯" if EXAM is None else f"{EXAM:,}"
s_q33 = "◯" if Q33 is None else str(Q33)

# 各社の予想 (10/25 時点) : (名前, 表記, 当たりとみなす点数の集合)
PRED = [
 ("TAC", "34点±1点", {33, 34, 35}), ("日建学院", "34点±1点", {33, 34, 35}), ("LEC", "34点±1点", {33, 34, 35}),
 ("フォーサイト", "34点±1点", {33, 34, 35}), ("大原", "33・34点", {33, 34}), ("住宅新報", "33点前後", {33}),
 ("大栄", "33・34点", {33, 34}), ("アガルート", "34点／32点（講師2人）", {32, 34}), ("ユーキャン", "32点±1点", {31, 32, 33}),
]
hits = [n for n, _, ok in PRED if SC in ok] if SC is not None else []
HIST = [("平成27年度", 31, "15.4%"), ("平成28年度", 35, "15.4%"), ("平成29年度", 35, "15.6%"), ("平成30年度", 37, "15.6%"),
        ("令和元年度", 35, "17.0%"), ("令和2年度（10月）", 38, "17.6%"), ("令和2年度（12月）", 36, "13.1%"),
        ("令和3年度（10月）", 34, "17.9%"), ("令和3年度（12月）", 34, "15.6%"), ("令和4年度", 36, "17.0%"),
        ("令和5年度", 36, "17.2%"), ("令和6年度", 37, "18.6%"), ("令和7年度", 33, "18.7%")]
MY = {q["n"]: q["answer"] for q in Q}
match = [n for n in ANS if MY.get(n) == ANS[n]]
diff = sorted(n for n in ANS if MY.get(n) != ANS[n])

def vs_last():
    if SC is None: return "去年の33点と比べて、◯点の差です。"
    d = SC - 33
    return "去年と同じ33点です。" if d == 0 else (f"去年の33点より{d}点高くなりました。" if d > 0 else f"去年の33点より{-d}点低く、平成27年度以来の低さです。" if SC <= 32 else f"去年の33点より{-d}点低くなりました。")

# 1 表紙
slide("", f"""<div class='cover'><h2>【速報】令和8年度 宅建<br>合格点は <span style='color:#c0392b'>{s_sc}点</span></h2>
<h3>合格率・合格者数・各社予想との答え合わせ・割れ問33の正解<br>合格した人／届かなかった人の、今日からやること</h3>
<p>※ 2026年11月25日（水）9時30分 不動産適正取引推進機構の発表にもとづく</p></div>""",
 f"令和8年度、宅建士試験の合格発表がありました。合格点は、50問中{s_sc}点です。この動画では、合格率と合格者数、各社の予想との答え合わせ、割れ問だった問33の正解、そして、合格した人と、届かなかった人が今日からやることを、まとめてお伝えします。")

# 2 結論
slide("結論｜合格点は50問中 " + s_sc + "点", f"""
<div class='big'>{s_sc}点<small>5問免除者は45問中 {s_mj}点</small></div>
<table><tr><th>項目</th><th class='c'>令和8年度</th><th class='c'>令和7年度</th></tr>
<tr><td>合格点</td><td class='c hi'>{s_sc}点</td><td class='c'>33点</td></tr>
<tr><td>合格率</td><td class='c'>{s_rate}%</td><td class='c'>18.7%</td></tr>
<tr><td>合格者数</td><td class='c'>{s_pass}人</td><td class='c'>45,821人</td></tr>
<tr><td>受験者数</td><td class='c'>{s_exam}人</td><td class='c'>245,462人</td></tr></table>""",
 f"結論です。令和8年度の合格点は、50問中{s_sc}点。5問免除の人は、45問中{s_mj}点です。{vs_last()}合格率は{s_rate}パーセント、合格者数は{s_pass}人、受験者数は{s_exam}人でした。")

# 3 各社予想との答え合わせ
rows = "".join(f"<tr><td>{n}</td><td class='c'>{t}</td><td class='c {'hi' if (SC is not None and SC in ok) else ('lo' if SC is not None else '')}'>"
               f"{'—' if SC is None else ('○ 的中' if SC in ok else '× 範囲外')}</td></tr>" for n, t, ok in PRED)
hit_txt = "◯社中◯社" if SC is None else f"{len(PRED)}社中{len(hits)}社"
slide("各社の予想との答え合わせ", f"""
<table><tr><th>会社</th><th class='c'>予想（10/25時点）</th><th class='c'>結果</th></tr>{rows}</table>
<div class='key'>予想の範囲内だったのは {hit_txt}</div>""",
 (f"各社の予想との答え合わせです。10月25日時点の予想で、範囲内だったのは{hit_txt}でした。"
  + ("" if SC is None else (f"的中したのは、{'、'.join(hits)}です。" if hits else "どの会社の予想も外れる結果になりました。"))
  + ("" if SC is None else ("多くの会社の予想の幅の中での決着でした。" if len(hits) * 2 >= len(PRED) else "今年は、予想の幅から外れた会社が多い結果になりました。合格点の予想は、毎年1点から2点ずれることがあります。"))))

# 4 推移
def _rows(items): return "".join(f"<tr><td>{y}</td><td class='c'>{p}点</td><td class='c'>{r}</td></tr>" for y, p, r in items)
_th = "<tr><th>年度</th><th class='c'>合格点</th><th class='c'>合格率</th></tr>"
_left = _rows(HIST[:7]); _right = _rows(HIST[7:]) + f"<tr class='now'><td>令和8年度</td><td class='c'>{s_sc}点</td><td class='c'>{s_rate}%</td></tr>"
slide("合格点の推移｜平成27年度〜令和8年度", f"""
<div class='two'><div><table>{_th}{_left}</table></div><div><table>{_th}{_right}</table></div></div>
<p class='note'>出典：不動産適正取引推進機構「試験実施概況」</p>""",
 f"合格点の推移です。平成27年度の31点がいちばん低く、令和2年10月の38点がいちばん高い年でした。去年、令和7年度は33点。今年は{s_sc}点です。個数問題と組合せ問題が増え、形式が変わった年は合格点が下がる傾向がありますが、合格率はおおむね15パーセントから19パーセントの間に保たれています。")

# 5 問33・正解番号
if ANS:
    ans_line = f"公式の正解番号と当チャンネルの独自解答の一致：<b>{len(ANS)}問中{len(match)}問</b>" + (f"（不一致：問{'・問'.join(map(str, diff))}）" if diff else "")
    ans_say = f"公式の正解番号と、当チャンネルの独自解答は、{len(ANS)}問中{len(match)}問が一致しました。" + (f"一致しなかったのは、問{'、問'.join(map(str, diff))}です。" if diff else "")
else:
    ans_line = "公式の正解番号と当チャンネルの独自解答の一致：◯◯問中◯◯問"; ans_say = ""
q33_res = "◯" if Q33 is None else ("4（正しいものはなし）" if Q33 == 4 else ("1（一つ）" if Q33 == 1 else str(Q33)))
q33_say = ("問33の公式の正解は、まだ空欄です。" if Q33 is None else
           (f"割れ問だった問33の公式の正解は、4、正しいものは、なし、でした。多数派の解答どおりです。4と答えた人は1点、1と答えた人は0点になります。" if Q33 == 4 else
            f"割れ問だった問33の公式の正解は、{Q33}でした。"))
slide("割れ問33の正解と、正解番号", f"""
<div class='key'>問33（専任の宅地建物取引士・個数問題）の公式の正解：<b>{q33_res}</b></div>
<table><tr><th>あなたの解答</th><th class='c'>問33の得点</th></tr>
<tr><td>4（なし）</td><td class='c {'hi' if Q33 == 4 else ''}'>{'—' if Q33 is None else ('1点' if Q33 == 4 else '0点')}</td></tr>
<tr><td>1（一つ）</td><td class='c {'hi' if Q33 == 1 else ''}'>{'—' if Q33 is None else ('1点' if Q33 == 1 else '0点')}</td></tr></table>
<p>{ans_line}</p>
<p class='note'>合格者の受験番号・合否判定基準・正解番号は、不動産適正取引推進機構のホームページに翌年7月末まで掲載されます</p>""",
 q33_say + ans_say + "正解番号は、機構のホームページで全50問を確認できます。")

# 6 合格した人へ (固定)
slide("合格した人へ｜今日からやること", """
<ul class='steps'>
<li><b>① 合格証書を待つ</b>──今日、簡易書留で発送。通常2〜4日で届く。不在票は7日以内に再配達</li>
<li><b>② 登録実務講習を申し込む</b>（実務経験2年未満の人）──約2万円。12月〜1月の開講分から埋まる</li>
<li><b>③ 書類を取り寄せる</b>──本籍地の市区町村（身分証明書）、法務局（登記されていないことの証明書）、住民票</li>
<li><b>④ 受験した都道府県に資格登録</b>──手数料37,000円、1〜2か月</li>
<li><b>⑤ 宅建士証の交付申請</b>──4,500円。<b>合格から1年以内なら法定講習は不要</b></li>
</ul>
<p class='note'>詳しい手順と費用は「合格発表の日に何をどう見るか」の動画で解説しています</p>""",
 "合格した人へ、今日からやることです。1、合格証書を待つ。今日、簡易書留で発送され、通常2日から4日で届きます。2、実務経験が2年未満の人は、登録実務講習を申し込む。約2万円で、12月から1月の開講分から埋まっていきます。3、本籍地の市区町村、法務局、住民票の書類を取り寄せる。4、受験した都道府県に資格登録を申請する。手数料は37,000円、1か月から2か月かかります。5、宅建士証の交付を申請する。4,500円です。合格から1年以内なら、法定講習は不要です。合格、おめでとうございます。")

# 7 届かなかった人へ (固定)
slide("届かなかった人へ｜今日のうちにやる3つのこと", """
<ul class='steps'>
<li><b>① 公式の正解番号で、分野別の得点を確定させる</b>──権利関係・法令上の制限・税その他・宅建業法・免除科目。点数は通知されないので、これが唯一の記録</li>
<li><b>② 「あと何点だったか」を書き残す</b>──1〜2点差なら知識は足りている。個数・組合せ問題の処理など、解き方の問題</li>
<li><b>③ 来年の日程を押さえる</b>──申込みは7月、試験は10月の第3日曜日（2027年10月17日の見込み）</li>
</ul>
<div class='key'>今年は個数10問・組合せ5問と形式が変わった年。答えを覚える勉強から、肢ごとに理由を言える勉強へ</div>""",
 "届かなかった人へ、今日のうちにやる3つのことです。1、公式の正解番号で、分野別の得点を確定させる。点数は通知されないので、これが唯一の記録になります。2、あと何点だったかを書き残す。1点、2点の差なら、知識は足りています。個数問題や組合せ問題の処理など、解き方の問題です。3、来年の日程を押さえる。申込みは7月、試験は10月の第3日曜日で、2027年は10月17日の見込みです。今年は形式が変わった年でした。答えを覚える勉強から、肢ごとに理由を言える勉強へ切り替えるのが、来年への最短距離です。")

# 8 まとめ
slide("まとめ", f"""
<ul class='steps'>
<li>令和8年度の合格点は <b>50問中{s_sc}点</b>（5問免除者は45問中{s_mj}点）</li>
<li>合格率 {s_rate}%、合格者数 {s_pass}人、受験者数 {s_exam}人</li>
<li>各社の予想（10/25時点）の範囲内は {hit_txt}</li>
<li>割れ問33の公式の正解は <b>{q33_res}</b></li>
<li>合格した人は、登録実務講習と書類の準備を今日から。1年以内に宅建士証まで進めば法定講習は不要</li>
<li>届かなかった人は、分野別の得点と「あと何点」を記録して、来年7月の申込みへ</li>
</ul>""",
 f"まとめです。令和8年度の合格点は、50問中{s_sc}点、5問免除の人は45問中{s_mj}点でした。合格率は{s_rate}パーセント、合格者数は{s_pass}人。各社の予想の範囲内は{hit_txt}、割れ問33の公式の正解は{q33_res}でした。受験された皆さん、本当にお疲れさまでした。この動画が参考になったら、チャンネル登録をお願いします。")

def youtube_text():
    title = f"【速報】令和8年度 宅建 合格点は{s_sc}点｜合格率{s_rate}%・各社予想の答え合わせ・割れ問33の正解・合格後にやること"
    desc = f"""令和8年度（2026年10月18日実施）宅建士試験の合格発表（2026年11月25日 9時30分）の速報です。

▼結果
・合格点：50問中{s_sc}点（5問免除者は45問中{s_mj}点）
・合格率：{s_rate}%
・合格者数：{s_pass}人／受験者数：{s_exam}人
・割れ問33の公式の正解：{q33_res}
・各社の合格点予想（10/25時点）の範囲内：{hit_txt}

▼目次
00:00 はじめに
（目次は動画の書き出し後に自動計算して追記）

▼関連動画
・合格発表の日に何をどう見るか（合格後の手順と費用） → （URL）
・割れ問「問33」正解は1か4か → （URL）
・合格点予想まとめ 第2弾 → （URL）

#宅建 #宅建士 #令和8年度 #宅建試験 #合格発表 #合格点 #合格率 #宅建2026"""
    tags = "宅建, 宅建士, 令和8年度 宅建, 2026 宅建, 宅建 合格発表, 宅建 合格点, 宅建 合格点 2026, 宅建 合格率, 宅建 問33, 宅建 割れ問, 宅建 合格後, 宅建 登録実務講習"
    return title, desc, tags

def chapters():
    t, out = 0.0, []
    for i, (title, *_rest) in enumerate(G.SLIDES, 1):
        f = os.path.join(G.OUT, f"s{i:02d}.mp4")
        if not os.path.exists(f): return None
        out.append(f"{int(t)//60:02d}:{int(t)%60:02d} {title or 'はじめに'}"); t += V.dur(f)
    return "\n".join(out)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--only", type=int); ap.add_argument("--preview", action="store_true"); a = ap.parse_args()
    if a.preview:
        from PIL import Image
        ims = []
        for i, (title, sub, body, speech) in enumerate(G.SLIDES, 1):
            png, h = G.render(body, title, sub, f"pv{i:02d}"); ims.append(Image.open(png).crop((0, 0, 1920, 1080)).resize((640, 360)))
        sheet = Image.new("RGB", (640 * 3, 360 * ((len(ims) + 2) // 3)), "gray")
        for k, im in enumerate(ims): sheet.paste(im, ((k % 3) * 640, (k // 3) * 360))
        p = os.path.join(G.OUT, "preview.png"); sheet.save(p); print("preview:", p)
    else:
        G.build(a.only, name="R8_sokuhou")
        title, desc, tags = youtube_text(); ch = chapters()
        if ch: desc = desc.replace("00:00 はじめに\n（目次は動画の書き出し後に自動計算して追記）", ch)
        p = os.path.join(G.OUT, "youtube.txt"); open(p, "w", encoding="utf-8").write(f"【タイトル】\n{title}\n\n【概要欄】\n{desc}\n\n【タグ】\n{tags}\n")
        print("youtube:", p)
