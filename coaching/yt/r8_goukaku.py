# -*- coding: utf-8 -*-
"""令和8年度 宅建 合格点予想まとめ 動画 (1920x1080, スライド＋ナレーション)
  python3 r8_goukaku.py [--only N]
"""
import argparse, html, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import vkit as V
from vkit import tts, dur, scroll_expr, speakable, W, H, FPS
from weasyprint import HTML
from PIL import Image, ImageOps

OUT = os.path.join(V.OUT, "goukaku"); os.makedirs(OUT, exist_ok=True)
CSS = """
@page { size: 508mm 3000mm; margin: 0; }
body { width: 1920px; box-sizing: border-box; margin: 0; padding: 50px 110px 120px; font-family: "Noto Sans CJK JP", sans-serif; font-size: 34px; line-height: 1.6; color: #111; background: #fff; }
h1 { font-size: 54px; color: #1a3d7c; margin: 0 0 24px; padding-bottom: 12px; border-bottom: 5px solid #1a3d7c; }
h1 small { font-size: 28px; color: #666; font-weight: normal; margin-left: 24px; }
.key { background: #fff3c4; border-left: 14px solid #e0a800; padding: 16px 28px; margin: 0 0 26px; font-size: 38px; font-weight: bold; line-height: 1.5; }
table { border-collapse: collapse; width: 100%; font-size: 32px; margin: 0 0 24px; }
th, td { border: 2px solid #333; padding: 10px 18px; vertical-align: top; text-align: left; line-height: 1.45; }
th { background: #1a3d7c; color: #fff; font-weight: bold; }
td:first-child, th:first-child { white-space: nowrap; }
td.c, th.c { text-align: center; }
td.hi { background: #ffe8e4; font-weight: bold; }
td.lo { background: #e8f0ff; }
tr.now td { background: #fff3c4; font-weight: bold; }
ul { margin: 0 0 20px; padding-left: 44px; } li { margin: 8px 0; }
.two { display: flex; gap: 40px; } .two > div { flex: 1; min-width: 0; }
.two td:first-child, .two th:first-child { white-space: normal; }
.note { color: #666; font-size: 26px; margin-top: 10px; }
.big { font-size: 120px; font-weight: bold; color: #c0392b; text-align: center; margin: 30px 0 10px; line-height: 1.1; }
.big small { font-size: 44px; color: #333; display: block; margin-top: 10px; }
.cover { text-align: center; padding-top: 250px; }
.cover h2 { font-size: 86px; color: #1a3d7c; margin: 0 0 30px; }
.cover h3 { font-size: 50px; font-weight: normal; margin: 0 0 50px; }
.cover p { font-size: 32px; color: #666; }
.steps li { margin: 14px 0; font-size: 34px; }
"""
def E(s): return html.escape(s)

SLIDES = []
def slide(title, body, speech, sub=""):
    SLIDES.append((title, sub, body, speech))

# 1 表紙
slide("", "<div class='cover'><h2>令和8年度（2026年）宅建士試験<br>合格点予想まとめ</h2><h3>各社の予想・難易度の講評・過去10年の合格点<br>自己採点のあと、11月25日までにやること</h3><p>※ 各社の予想は10月22日時点の公式発表から。正式な合格点は11月25日（水）9時30分の合格発表で公表されます。</p></div>",
 "令和8年度、2026年の宅地建物取引士試験、お疲れさまでした。この動画では、主な予備校・通信講座が発表した合格点の予想と、難易度の講評、過去10年の合格点、そして自己採点のあと、11月25日の合格発表までにやっておくことを、表を使って整理します。各社の予想は10月22日時点の公式発表をもとにしています。正式な合格点と正解番号が公表されるのは、11月25日水曜日、午前9時30分の合格発表です。それまでに出る数字は、すべて非公式の見込みとして見てください。")

# 2 結論
slide("結論｜今年の予想ラインは32〜34点が中心", """
<div class='big'>32〜34点<small>±1点の幅まで含めると 31〜35点（6社の公式発表から）</small></div>
<ul><li>TAC・日建学院・LEC・フォーサイト ＝ <b>34点±1点</b></li><li>ユーキャン ＝ <b>32点±1点</b></li><li>アガルート ＝ 講師2人が <b>34点</b> と <b>32点</b></li><li>大原は10月24日（土）20時の予想会で発表予定。総合資格学院は採点サービス利用者にメールで案内</li></ul>
<div class='note'>去年（令和7年度）の合格点は33点。過去10年では33〜38点の範囲で動いています。</div>""",
 "まず結論です。現時点の予想の中心は、32点から34点です。TAC、日建学院、LEC、フォーサイトの4社が34点プラスマイナス1点。ユーキャンが32点プラスマイナス1点。アガルートは講師2人が、それぞれ34点と32点を出しています。プラスマイナス1点の幅まで含めると、31点から35点になります。大原は10月24日土曜日20時の予想会で発表予定、総合資格学院は採点サービスの利用者にメールで案内しています。去年、令和7年度の合格点は33点でしたので、今年もその前後、というのが各社の見方です。")

# 3 一覧表
slide("各社の合格点予想一覧", """
<table><tr><th>会社</th><th class='c'>合格点予想</th><th>発表の予定・方法</th></tr>
<tr><td>TAC</td><td class='c hi'>34点±1点</td><td>公式ページで公開済み</td></tr>
<tr><td>日建学院</td><td class='c hi'>34点±1点</td><td>公式ページで公開済み</td></tr>
<tr><td>LEC</td><td class='c hi'>34点±1点</td><td>解答速報PDFで公開（10/18 18時時点）。10/25（日）11時から合格基準点予想会</td></tr>
<tr><td>フォーサイト</td><td class='c hi'>34点±1点</td><td>公式ページ（解答速報・試験講評）で公開済み</td></tr>
<tr><td>ユーキャン</td><td class='c lo'>32点±1点</td><td>公式ページで公開済み（20時05分）</td></tr>
<tr><td>アガルート</td><td class='c'>34点（工藤講師・35点の可能性も）<br>32点（林講師）</td><td>公式YouTubeの合格ライン予想ライブで講師2人が発表</td></tr>
<tr><td>大原</td><td class='c'>未発表</td><td>10/24（土）20時の合格ライン予想会で発表予定</td></tr>
<tr><td>総合資格学院</td><td class='c'>ページには非掲載</td><td>即日採点サービスの利用者にメールで案内</td></tr></table>
<div class='note'>予想は会社ごとに1〜2点ずれることがよくあります。1社だけで判断せず、複数社の予想の幅で見ておきましょう。LECの推定点は再現答案をもとにしたもので、集まる解答が増えると変わる可能性があります。</div>""",
 "各社の予想を一覧にしました。TAC、日建学院、LEC、フォーサイトが34点プラスマイナス1点で並んでいます。ユーキャンだけが32点プラスマイナス1点と、2点低い予想です。アガルートは、工藤講師が34点、35点の可能性もあるとし、林講師は32点としています。大原は10月24日の予想会で発表予定、総合資格学院はページには載せず、即日採点サービスの利用者にメールで案内しています。予想は会社ごとに1点から2点ずれることがよくあります。1社の数字だけで一喜一憂せず、複数社の幅で見ておくと、発表日まで余計に揺さぶられずにすみます。LECの推定点は、解答速報会に出席した人の再現答案をもとに出したもので、集まる解答が増えるにつれて変わる可能性があると書かれています。ほかの会社も、予告なく変わることがあるとしています。")

# 4 講評
slide("今年は難しかった？｜各社の講評", """
<div class='key'>3社とも「解きにくい・やや難しい試験」。個数問題10問、組合せ問題5問（史上最多）、問題冊子は27→25ページ</div>
<table><tr><th>分野</th><th>ユーキャン</th><th>日建学院</th></tr>
<tr><td>全体</td><td>得点が伸びにくい試験</td><td>昨年と同様にやや難しかった</td></tr>
<tr><td>権利関係</td><td>昨年度より平均点がかなり下がった</td><td>やや難しかった</td></tr>
<tr><td>宅建業法</td><td>昨年度より平均点がかなり下がった</td><td>昨年と同様にやや難しかった</td></tr>
<tr><td>法令上の制限</td><td>昨年度に続き、例年より平均点が低い</td><td>やや易しかった</td></tr>
<tr><td>税・価格の評定</td><td>昨年度より大幅に平均点が上がった</td><td>やや易しかった</td></tr></table>
<div class='note'>TACのライブでは「時間を取られ体力を奪われる試験。ただし点数は去年より上がる」との見方。視聴者アンケートでは7割が「難しかった」、いちばん難しかった科目は民法（権利関係）、問1の所有者不明土地に戸惑った人が多数。</div>""",
 "今年の試験は難しかったのでしょうか。ユーキャン、日建学院、TACの3社とも、解きにくい、やや難しい試験だったという見方です。ポイントは3つ。正しいものはいくつあるかを問う個数問題が10問と、去年の11問に続いて多かったこと。組合せ問題が5問で、ユーキャンは史上最多としています。宅建業法では去年の1問から4問に増えました。そして問題冊子が去年の27ページから25ページに減ったことです。分野別に見ると、ユーキャンは権利関係と宅建業法の平均点がかなり下がった、法令上の制限は例年より低い、税・価格は大幅に上がったとしています。日建学院は、権利関係と宅建業法がやや難しく、法令上の制限と税はやや易しかったという評価です。TACの講師陣は、時間を取られ体力を奪われる試験だった、ただし点数は去年より上がると見ています。配信中のアンケートでは7割ほどが難しかったと答え、いちばん難しかった科目は民法、特に問1の所有者不明土地の問題に戸惑った人が多かったそうです。")

# 5 なぜ2点差
slide("なぜ34点と32点で分かれたのか", """
<div class='two'><div><table><tr><th>TAC・日建学院</th></tr><tr><td>解きにくい試験だったが、<b>点数は去年より取れている</b><br>→ 去年の33点より1点上の <b>34点±1点</b></td></tr></table></div>
<div><table><tr><th>ユーキャン</th></tr><tr><td>分野ごとの平均点の上がり下がりを差し引くと<b>去年より1点以上マイナス</b><br>→ 去年の33点より1点下の <b>32点±1点</b></td></tr></table></div></div>
<div class='key'>「解きにくい」は共通。違いは「去年と比べて点が取れているか」の見方</div>
<div class='note'>出典：ユーキャン「解答速報・合格ライン」、日建学院「解答速報」総評、TAC公式YouTube解答速報ライブ、アガルート公式YouTube合格ライン予想ライブ</div>""",
 "では、なぜ34点と32点で予想が分かれたのでしょうか。3社とも、解きにくい試験という点は同じです。違いは、去年と比べて点数が取れているかの見方です。TACと日建学院は、それでも点数は去年より取れていると見て、去年の33点より1点上の34点。ユーキャンは、平均点が上がった分野と下がった分野を差し引くと、去年より1点以上マイナスになるとして、1点低い32点を予想しています。つまり、受験生の平均点が去年より上なのか下なのか、ここの読みが2点の差になっているわけです。")

# 6 過去5年の予想と実際
slide("各社の予想はどれくらい当たる？｜令和3〜7年度", """
<table><tr><th class='c'>年度</th><th class='c'>実際の合格点</th><th class='c'>予想の範囲内だった社数</th></tr>
<tr><td class='c'>令和7年度</td><td class='c'>33点</td><td class='c'>6社中4社（大原・フォーサイトは範囲外）</td></tr>
<tr><td class='c'>令和6年度</td><td class='c'>37点</td><td class='c'>5社中4社（TACは35点±1で範囲外）</td></tr>
<tr><td class='c'>令和5年度</td><td class='c'>36点</td><td class='c'>5社中4社（大原は範囲外）</td></tr>
<tr><td class='c'>令和4年度</td><td class='c'>36点</td><td class='c'>5社中5社</td></tr>
<tr><td class='c'>令和3年度（10月）</td><td class='c'>34点</td><td class='c'>5社中3社（大原・フォーサイトは範囲外）</td></tr></table>
<ul><li>確認できた26件のうち、予想の範囲内 <b>20件</b>、範囲外 6件</li><li>範囲外6件のうち5件は、実際の合格点が予想の幅より<b>低かった</b>ケース（高かったのは令和6年度のTACの1件だけ）</li><li>令和3・5・7年度は、実際の合格点が各社の予想の中心と同じか、それより低かった</li></ul>""",
 "各社の予想は、どのくらい当たるものなのでしょうか。令和3年度から7年度までの5回分を、当時の公式ページの予想と実際の合格点で比べると、確認できた26件のうち、予想の範囲内だったのが20件、範囲外が6件でした。令和4年度は5社すべてが的中。令和7年度は6社中4社、令和6年度と5年度は5社中4社でした。注目したいのは、外れた6件のうち5件が、実際の合格点が予想の幅より低かったケースだという点です。予想より高くなったのは、令和6年度のTACの1件だけです。令和3年度、5年度、7年度は、実際の合格点が各社の予想の中心と同じか、それより低くなりました。特に去年、令和7年度は、6社すべての予想の中心を、実際の33点が下回っています。予想の幅の下のほうにいる人も、望みを捨てるのは早いということです。")

# 7 過去10年の合格点・合格率
slide("過去10年の合格点と合格率", """
<div class='two'><div><table><tr><th class='c'>年度</th><th class='c'>合格点</th><th class='c'>合格率</th></tr>
<tr><td>令和7年度</td><td class='c hi'>33点</td><td class='c'>18.7%</td></tr><tr><td>令和6年度</td><td class='c'>37点</td><td class='c'>18.6%</td></tr>
<tr><td>令和5年度</td><td class='c'>36点</td><td class='c'>17.2%</td></tr><tr><td>令和4年度</td><td class='c'>36点</td><td class='c'>17.0%</td></tr>
<tr><td>令和3年度（12月）</td><td class='c'>34点</td><td class='c'>15.6%</td></tr><tr><td>令和3年度（10月）</td><td class='c'>34点</td><td class='c'>17.9%</td></tr></table></div>
<div><table><tr><th class='c'>年度</th><th class='c'>合格点</th><th class='c'>合格率</th></tr>
<tr><td>令和2年度（12月）</td><td class='c'>36点</td><td class='c'>13.1%</td></tr><tr><td>令和2年度（10月）</td><td class='c hi'>38点</td><td class='c'>17.6%</td></tr>
<tr><td>令和元年度</td><td class='c'>35点</td><td class='c'>17.0%</td></tr><tr><td>平成30年度</td><td class='c'>37点</td><td class='c'>15.6%</td></tr>
<tr><td>平成29年度</td><td class='c'>35点</td><td class='c'>15.6%</td></tr><tr><td>平成28年度</td><td class='c'>35点</td><td class='c'>15.4%</td></tr></table></div></div>
<div class='key'>合格点は33〜38点、合格率は13〜19%。12回分の平均は35.5点。去年の33点はこの10年でいちばん低い</div>
<div class='note'>出典：不動産適正取引推進機構「試験実施概況（令和7年度以前10年間）」</div>""",
 "次に、過去10年の合格点と合格率です。合格点は毎年変わり、試験の前には公表されません。過去10年、12回分を見ると、合格点は33点から38点のあいだで動いています。いちばん高かったのは令和2年度10月試験の38点、いちばん低かったのは去年、令和7年度の33点です。12回分の平均は35.5点。一方、合格率は13パーセントから19パーセントほどで、合格点が高い年も低い年も、合格率は大きくは変わっていません。つまり、その年の問題の難しさに合わせて、合格点が上下していると読み取れます。各社の予想が、去年より平均点が上がったか下がったかを手がかりにしているのは、このためです。")

# 8 受験者数・5問免除
slide("受験者数・合格者数・5問免除の合格点", """
<table><tr><th class='c'>年度</th><th class='c'>受験者数</th><th class='c'>合格者数</th><th class='c'>合格点（一般）</th><th class='c'>5問免除（45問中）</th></tr>
<tr><td>令和7年度</td><td class='c'>245,462人</td><td class='c'>45,821人</td><td class='c'>33点</td><td class='c'>28点</td></tr>
<tr><td>令和6年度</td><td class='c'>241,436人</td><td class='c'>44,992人</td><td class='c'>37点</td><td class='c'>32点</td></tr>
<tr><td>令和5年度</td><td class='c'>233,276人</td><td class='c'>40,025人</td><td class='c'>36点</td><td class='c'>31点</td></tr>
<tr><td>令和4年度</td><td class='c'>226,048人</td><td class='c'>38,525人</td><td class='c'>36点</td><td class='c'>31点</td></tr>
<tr><td>令和3年度（10月）</td><td class='c'>209,749人</td><td class='c'>37,579人</td><td class='c'>34点</td><td class='c'>29点</td></tr>
<tr><td>令和2年度（10月）</td><td class='c'>168,989人</td><td class='c'>29,728人</td><td class='c'>38点</td><td class='c'>33点</td></tr>
<tr><td>令和元年度</td><td class='c'>220,797人</td><td class='c'>37,481人</td><td class='c'>35点</td><td class='c'>30点</td></tr></table>
<ul><li>令和7年度の受験者は245,462人（申込者の約80%）、合格者45,821人はこの10年で最多</li><li>5問免除の合格点は、数字が示された11回すべてで一般の合格点から<b>ちょうど5点低い</b>。各社の予想から5点引いた点数を目安に</li></ul>""",
 "受験者数と合格者数も見ておきましょう。去年、令和7年度の受験者は24万5千人あまりで、申込者の約8割が受験しました。合格者は4万5千8百人あまりで、この10年でいちばん多い人数です。登録講習を修了して5問免除で受けた人は、問1から問45の45問が採点の対象で、合格点も別に示されます。過去の公表結果を見ると、5問免除の合格点は、数字が示された11回すべてで、一般の合格点からちょうど5点低い点数でした。去年は一般が33点、5問免除が28点です。各社の予想が50問中何点、という形で出ている場合は、そこから5点引いた点数を目安にしてください。ただし、今年も同じになるかは、合格発表まで分かりません。")

# 9 合格点はどう決まる
slide("合格点はどう決まる？｜公式に書かれていること", """
<ul><li><b>試験の基準</b>──「宅地建物取引業に関する実用的な知識を有するかどうかを判定することに基準が置かれている」（宅建業法施行規則第7条）</li>
<li><b>合格点の公表</b>──合格発表の日に、合格者の受験番号・正解番号とともに「合否判定基準」が掲載される</li>
<li><b>問い合わせ</b>──試験問題の内容や受験者ごとの合否についての問い合わせには回答しない</li></ul>
<div class='key'>合格点をどう決めているかは公式には書かれていない。「合格率で決めている」という説明も公式のものではない</div>
<div class='note'>そのうえで数字を見ると、合格点は33〜38点と5点の幅で動き、合格率は13.1〜18.7%。各社は「去年より平均点が上がったか下がったか」を手がかりに予想している。</div>""",
 "そもそも合格点は、どう決まっているのでしょうか。試験を実施する不動産適正取引推進機構は、試験前にも試験後すぐにも、合格点を示しません。公式資料に書かれているのは、試験の基準が、宅地建物取引業に関する実用的な知識を有するかどうかの判定に置かれていること、合格発表の日に合否判定基準が掲載されること、そして、試験問題の内容や合否についての問い合わせには回答しないこと、この3点です。合格点をどのような方法で決めているかは書かれていません。合格率で決めている、といった説明も、公式に示されたものではありません。そのうえで数字を見ると、合格点は5点の幅で動き、合格率は13パーセントから19パーセントに収まっています。")

# 10 自己採点の手順
slide("自己採点のやり方｜5つの手順", """
<ol class='steps'><li><b>問題冊子に書いた自分の解答を確認する</b>──書き写していない問題は「不明」として分けておく</li>
<li><b>2〜3社の解答速報と照らし合わせる</b>──各社の正解番号は独自の判断で、あとから変わることがある</li>
<li><b>社によって正解が分かれた問題に印をつける</b>──「正解なら＋1点」として点数を幅で持っておく</li>
<li><b>分野ごとに集計する</b>──権利関係・法令上の制限・税・宅建業法・免除科目。来年受ける場合もそのまま使える</li>
<li><b>5問免除の人は問46〜50を除く</b>──45問中の点数で、予想点から5点引いた数字と比べる</li></ol>
<div class='note'>採点サービスに解答を入力しておくと、各社が合格点予想を出すときの材料にもなります（TAC Web採点、日建学院 即日Web採点、大原、総合資格学院など）。</div>""",
 "ここからは、自己採点のあとにやることです。まず、自分の点数をできるだけ正確に出しておきましょう。手順は5つ。1、問題冊子に書いた自分の解答を確認する。書き写していない問題は、不明として分けておきます。2、2社から3社の解答速報と照らし合わせる。各社の正解番号は独自の判断で、あとから変わることがあります。3、社によって正解が分かれた問題に印をつける。割れた問題は、正解ならプラス1点として、点数を幅で持っておきます。4、分野ごとに集計する。権利関係、法令上の制限、税、宅建業法、免除科目に分けて数えます。来年また受ける場合にも、この集計がそのまま使えます。5、5問免除の人は問46から問50を除いて、45問中の点数で、予想点から5点引いた数字と比べます。難しい問題では、社によって正解の番号が分かれることがあります。点数は、何点から何点、と幅で持っておくのがおすすめです。")

# 11 点数別
slide("自己採点の点数別｜11月25日までにやること", """
<table><tr><th class='c'>自己採点（50問）</th><th>合格発表までにやること</th></tr>
<tr><td class='c hi'>36点以上</td><td>各社の予想の幅より上。登録の要件（実務経験2年以上か、登録実務講習が必要か）を確認し、登録実務講習の日程を調べておく</td></tr>
<tr class='now'><td class='c'>31〜35点</td><td>予想の幅の中。合格・不合格の両方に備える。割れた問題を整理し、各社の予想会（大原 10/24、LEC 10/25）のあとの数字も確認する</td></tr>
<tr><td class='c lo'>30点以下</td><td>予想の幅より下。分野ごとの得点が記憶に新しいうちに書き出し、来年の試験日程と講座の割引条件を確認しておく</td></tr></table>
<div class='key'>予想ラインの前後にいる人は「合格していた場合」と「届かなかった場合」の両方の準備を並行して</div>
<div class='note'>5問免除の人は、表の点数から5点引いた数字（45問中）で読み替えてください。どの点数でも、合否は11月25日の発表まで確定しません。</div>""",
 "自己採点の点数別に、合格発表までにやることを整理します。36点以上の人は、各社の予想の幅より上です。登録の要件、つまり実務経験が2年以上あるか、登録実務講習が必要かを確認して、講習の日程を調べておきましょう。31点から35点の人は、予想の幅の中です。合格と不合格の両方に備えてください。割れた問題を整理し、大原の10月24日、LECの10月25日の予想会のあとの数字も確認しましょう。30点以下の人は、予想の幅より下です。分野ごとの得点が記憶に新しいうちに書き出して、来年の試験日程と講座の割引条件を確認しておきます。予想ラインの前後にいる人は、合格していた場合の登録の流れと、届かなかった場合の弱点の書き出し、この2つを並行して進めておくと、どちらに転んでも動けます。")

# 12 合格発表
slide("合格発表は11月25日（水）9時30分", """
<ul><li>不動産適正取引推進機構のホームページに、<b>合格者の受験番号・合否判定基準（合格点）・正解番号</b>が掲載</li>
<li>合格者には<b>合格証書</b>が簡易書留で発送（当日に届くとは限らない）。不在のときはご不在連絡票で郵便局へ</li>
<li><b>不合格の通知はない</b></li>
<li>令和8年度から、インターネット申込みの人は<b>マイページで自分の得点・選んだ番号</b>を見られる予定（11月26日〜令和9年3月31日の予定、郵送申込みは対象外）</li>
<li>発表日の決まり方は「試験日の26日（土日祝を除く）後の日」。受験票は合格発表のあとも<b>保管必須</b></li></ul>
<div class='note'>出典：不動産適正取引推進機構「試験スケジュール」「よくあるご質問」「令和8年度 試験案内」</div>""",
 "合格発表は、11月25日水曜日、午前9時30分です。機構のホームページに、合格者の受験番号、合否判定基準つまり合格点、そして正解番号が掲載されます。合格者には合格証書が簡易書留で発送されますが、当日に届くとは限りません。不合格だった人への通知はありません。今年度から、インターネットで申し込んだ人は、合格発表のあとマイページで自分の得点や、各問で選んだ番号を見られる予定です。郵送で申し込んだ人は対象外です。受験票は、合格発表のあとも手元に残しておいてください。")

# 13 合格していたら・届かなかったら
slide("合格していたら｜届かなかったら", """
<div class='two'><div><table><tr><th>合格していたら｜登録から宅建士証まで</th></tr><tr><td>
1. 合格証書を受け取る（登録手続の案内が同封）<br>2. 登録の要件を満たす（実務経験2年未満なら<b>登録実務講習</b>を修了）<br>3. <b>受験した都道府県</b>で資格登録を申請（住所地ではない）<br>4. 宅建士証の交付（有効期間5年。合格から1年を超えると法定講習が必要）</td></tr></table></div>
<div><table><tr><th>届かなかったら｜2027年度試験の目安</th></tr><tr><td>
実施公告：6月の第1金曜日<br>インターネット申込み：7月上旬〜下旬<br>試験日：10月の第3日曜日 → <b>2027年10月17日（日）</b>の見込み<br>合格発表：11月下旬<br>受験手数料：8,200円。申込みは住んでいる都道府県</td></tr></table></div></div>
<div class='key'>試験に合格しただけでは、まだ「宅地建物取引士」ではない。資格登録と宅建士証の交付まで必要</div>""",
 "合格していたら、どうなるのか。宅建試験に合格しただけでは、まだ宅地建物取引士ではありません。流れは4つです。合格証書を受け取る。宅建業の実務経験が2年以上ない人は、登録実務講習を修了する。受験した都道府県で資格登録を申請する。登録先は住んでいる都道府県ではなく、受験した試験地の都道府県です。そして宅建士証の交付を受ける。有効期間は5年で、合格から1年を超えて申請する場合は法定講習が必要です。届かなかった場合は、来年の日程を押さえておきましょう。宅建試験は毎年1回、10月の第3日曜日です。例年どおりなら、2027年度の試験日は2027年10月17日、日曜日になります。申込みは7月。時期を逃すと1年待つことになるので、6月ごろから機構のホームページを確認しておくと安心です。")

# 14 まとめ
slide("まとめ", """
<ul><li>予想の中心は<b>32〜34点</b>、幅は31〜35点。大原（10/24）・LEC予想会（10/25）のあとに数字が動くことも</li>
<li>各社の予想は過去5年で26件中20件が的中。外れたときは<b>実際のほうが低い</b>ことが多い</li>
<li>合格点は33〜38点、合格率は13〜19%で推移。去年の33点は10年で最低</li>
<li>5問免除は一般から<b>5点低い</b>のがこれまでの全例</li>
<li>自己採点は2〜3社で、割れた問題は幅で。分野別に集計しておく</li>
<li>正式な合格点・正解番号は<b>11月25日（水）9時30分</b></li></ul>
<div class='note'>この動画は、各社の公式発表と不動産適正取引推進機構の公表資料をまとめた記事（イング資格取得ラボ、10月22日更新）をもとに構成しています。各社の予想は非公式の見込みです。</div>""",
 "最後にまとめです。今年の予想の中心は32点から34点、幅は31点から35点です。大原とLECの予想会のあとに数字が動くこともあります。各社の予想は過去5年で26件中20件が的中していますが、外れるときは実際の合格点のほうが低いことが多いです。合格点は33点から38点、合格率は13パーセントから19パーセントで推移していて、去年の33点はこの10年で最低でした。5問免除の合格点は、これまで全例で一般から5点低い数字です。自己採点は2社から3社の速報で、割れた問題は幅で持ち、分野別に集計しておきましょう。正式な合格点と正解番号が出るのは、11月25日水曜日、午前9時30分です。それまでは、合格していた場合と届かなかった場合、両方の準備を進めておいてください。ご視聴ありがとうございました。")

def _render_once(head, body, name, scale):
    """ページ幅を W/scale にして描き、解像度を scale 倍にして W px の画像にする → 文字が scale 倍になる"""
    pw = W / scale
    ph_mm = 3000 if scale == 1.0 else (H * 1.3 / scale) / 96 * 25.4   # 拡大時は収まるか見るだけなので短いページで十分 (速い)
    css = CSS.replace("size: 508mm 3000mm", f"size: {pw/96*25.4:.2f}mm {ph_mm:.1f}mm").replace("width: 1920px", f"width: {pw:.0f}px")
    pdf = os.path.join(OUT, name + ".pdf"); png = os.path.join(OUT, name + ".png")
    HTML(string=f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{head}{body}</body></html>").write_pdf(pdf)
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", f"{96*scale:.3f}", "-png", "-singlefile", pdf, png[:-4]], check=True)
    im = Image.open(png).convert("RGB")
    if im.size[0] != W: im = im.resize((W, int(im.size[1] * W / im.size[0])))
    bbox = ImageOps.invert(im.convert("L")).point(lambda v: 255 if v > 55 else 0).getbbox()
    content_h = (bbox[3] if bbox else 0)
    return im, content_h, png

def render(body, title, sub, name):
    head = f"<h1>{E(title)}<small>{E(sub)}</small></h1>" if title else ""
    avail = H - (V.BAND if V.HIGHLIGHT else 0) - 70        # 字幕帯と下余白を除いた高さ
    im, ch, png = _render_once(head, body, name, 1.0)
    if 0 < ch < avail * 0.85:                               # 下が空くなら文字を大きくして埋める (最大1.6倍)
        best = (im, ch, png)
        scale = min(1.6, avail / ch)
        for _ in range(5):                                  # 折り返しで高さが非線形に変わるので、収まるまで少しずつ下げる
            if scale < 1.08: break
            im2, ch2, png2 = _render_once(head, body, name, scale)
            if ch2 <= avail: best = (im2, ch2, png2); break
            scale = max(1.0, min(scale - 0.06, scale * avail / ch2))
        im, ch, png = best
        if png != best[2] or ch > avail: im, ch, png = _render_once(head, body, name, 1.0)
    bottom = max(H, min(im.size[1], ch + 90))
    im = im.crop((0, 0, W, bottom))
    if V.HIGHLIGHT:   # 字幕帯のぶん下に余白を足す
        pad = V.BAND - 90
        bg = Image.new('RGB', (W, bottom + pad), 'white'); bg.paste(im, (0, 0)); im = bg; bottom += pad
    im.save(png)
    return png, bottom

def build(only=None, name="R8_goukaku"):
    segs = []
    for i, (title, sub, body, speech) in enumerate(SLIDES, 1):
        if only and only != i: continue
        png, h = render(body, title, sub, f"s{i:02d}")
        mp3 = os.path.join(OUT, f"s{i:02d}.mp3")
        sents = V.split_sentences(speech)
        tp = tts(V.ssml_sentences(sents), mp3, ssml=True, rate=1.0)
        total = dur(mp3) + 1.5
        pts = [(2.0, 0), (total - 2.0, h - H)] if h > H else []
        out = os.path.join(OUT, f"s{i:02d}.mp4")
        V.encode_subtitled(png, mp3, scroll_expr(pts, max(0, h - H), total), total, sents, tp, out, OUT, f"s{i:02d}")
        print(f"slide {i:02d} {total:5.0f}s  page_h={h}  {title}", flush=True)
        segs.append(out)
    final = os.path.join(OUT, f"{name}{'_s'+str(only) if only else ''}.mp4")
    V.concat(segs, final)
    print("完了:", final, f"{os.path.getsize(final)/1e6:.1f}MB {dur(final)/60:.1f}分", flush=True)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--only", type=int); a = ap.parse_args()
    build(a.only)
