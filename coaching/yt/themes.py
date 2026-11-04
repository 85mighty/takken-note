# -*- coding: utf-8 -*-
"""スライドの見た目（テーマ）。字幕スタイル画面で選ぶ → sub_style.json の slide_theme に保存 → 次の出力から全スライドに反映。
  css(key)        … 基本 CSS の後ろに足す上書き CSS
  sample(key,out) … 見本画像（表＋ポイント枠の1枚と表紙を横に並べたもの）
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__)); FONTS = os.path.join(HERE, "fonts")
_SERIF = (f"@font-face{{font-family:'SlideSerif';font-weight:normal;src:url('file://{FONTS}/ShipporiMincho-Regular.ttf')}}"
          f"@font-face{{font-family:'SlideSerif';font-weight:bold;src:url('file://{FONTS}/ShipporiMincho-Bold.ttf')}}")

THEMES = {
 "navy": {"label": "기본 (남색·흰 바탕)", "font": "Zen角ゴシックNew",
          "desc": "지금까지의 디자인. 남색 제목선·남색 표 머리글", "css": ""},
 "wa": {"label": "和モダン (생성이 바탕·명조 제목·주홍)", "font": "Zen角ゴシックNew",
        "desc": "생성이색 종이 바탕, 제목은 명조체(しっぽり明朝)와 주홍 세로선, 표는 먹색 테두리. 차분한 일본 교양 프로그램 느낌",
        "css": _SERIF + """
body{background:#f8f5ec;color:#2b2b2b}
h1{font-family:'SlideSerif',serif;color:#1f2f4f;border-bottom:none;padding:4px 0 4px 28px;border-left:16px solid #b7282e;letter-spacing:.04em}
h1 small{color:#7a6e5f;font-family:'SlideSerif',serif}
th{background:#2d3e5f;color:#f8f5ec;border-color:#2d3e5f} th,td{border:1.5px solid #9a9183}
td.hi{background:#f3dcd5;color:#8f1d1d} td.lo{background:#e6ebe4} tr.now td{background:#f6e7c1}
.key{background:#fbf3df;border-left:14px solid #b7282e;color:#3a2a1a}
.big{color:#b7282e;font-family:'SlideSerif',serif}
.cover h2{font-family:'SlideSerif',serif;color:#1f2f4f;letter-spacing:.05em} .cover h3{color:#4a4a4a} .cover p,.note{color:#7a6e5f}
"""},
 "yobiko": {"label": "予備校プリント (흰 바탕·빨간 이중선·형광펜)", "font": "BIZ UDPゴシック",
            "desc": "일본 예비교 강의 프린트 느낌. 검정 굵은 글자, 빨간 이중 밑줄, 굵은 글자에 노란 형광펜, POINT 라벨",
            "css": """
body{background:#fff;color:#111}
h1{color:#111;border-bottom:6px double #d32f2f;padding-bottom:10px} h1 small{color:#555}
th{background:#f0f0f0;color:#111;border:3px solid #111} td{border:2px solid #111}
td.hi{background:#ffe0e0;color:#c62828} td.lo{background:#e8f4ff} tr.now td{background:#fff59d}
b{background:linear-gradient(transparent 62%,#fff176 62%)} th b,.ov b{background:none}
.key{background:#fffdf0;border:3px solid #111;border-left:3px solid #111;color:#111}
.key::before{content:"POINT";display:inline-block;background:#d32f2f;color:#fff;font-size:26px;padding:2px 16px;margin-right:18px;border-radius:4px;vertical-align:middle;letter-spacing:.1em}
.big{color:#d32f2f}
.cover h2{color:#111;border-bottom:8px double #d32f2f;display:inline-block;padding-bottom:12px} .cover h3{color:#333}
"""},
 "tv": {"label": "テレビ番組 (둥근 고딕·남색 띠·주황)", "font": "M PLUS Rounded",
        "desc": "일본 정보 프로그램 자막(テロップ) 느낌. 둥근 굵은 글자, 제목은 남색 띠에 주황 그림자, 표는 둥근 모서리·줄무늬",
        "css": """
body{background:#fffdf7;color:#1b1b1b}
h1{background:#0b2a5b;color:#fff;border-bottom:none;padding:14px 30px;border-radius:14px;box-shadow:8px 8px 0 #f08300;margin-bottom:36px} h1 small{color:#ffe08a}
table{border:4px solid #0b2a5b} th{background:#f08300;color:#fff;border:2px solid #f08300;border-bottom:4px solid #0b2a5b} td{border:2px solid #e8e2d4}
tr:nth-child(even) td{background:#fff6e5}
td.hi{background:#ffd6c2;color:#b43a00} td.lo{background:#d9ebff} tr.now td{background:#ffe066}
.key{background:#ffe066;border:4px solid #0b2a5b;border-left:4px solid #0b2a5b;border-radius:18px;color:#0b2a5b;padding:18px 30px}
.big{color:#e8480c} .note{color:#5a5a5a}
.cover h2{background:#0b2a5b;color:#fff;display:inline-block;padding:20px 50px;border-radius:20px;box-shadow:12px 12px 0 #f08300;margin-bottom:50px} .cover h3{color:#0b2a5b;font-weight:bold}
"""},
 "textbook": {"label": "参考書 (파랑 2색 인쇄·ポイント 라벨)", "font": "Zen角ゴシックNew",
              "desc": "일본 수험 참고서의 2색 인쇄 느낌. 파란 제목 띠, 연한 파랑 표 머리글, 중요한 곳만 빨강, ポイント 라벨",
              "css": """
body{background:#fff;color:#1a1a1a}
h1{color:#0b5ea8;border-bottom:none;border-left:18px solid #0b5ea8;padding:8px 0 8px 24px;background:#eaf3fb} h1 small{color:#4a6a86}
th{background:#d8e9f7;color:#0b4f8a;border:2px solid #0b5ea8} td{border:1.5px solid #7fb0d9}
td.hi{background:#ffecec;color:#c62828} td.lo{background:#eef5fb} tr.now td{background:#fff2cc}
.key{background:#fff;border:3px solid #0b5ea8;border-left:18px solid #0b5ea8;color:#0b4f8a}
.key::before{content:"ポイント";display:inline-block;background:#0b5ea8;color:#fff;font-size:26px;padding:2px 14px;border-radius:4px;margin-right:16px;vertical-align:middle}
.big{color:#c62828}
.cover h2{color:#0b5ea8} .cover h3{color:#333;border-top:3px solid #0b5ea8;border-bottom:3px solid #0b5ea8;display:inline-block;padding:14px 30px}
"""},
 "kokuban": {"label": "黒板＋白い紙 (解説系YouTube風·波線·赤枠)", "font": "Zen角ゴシックNew", "max_h": 840,
             "desc": "녹색 칠판 위에 목재 액자에 든 흰 종이. 큰 글자, 굵은 글자(b)에는 파란 물결 밑줄, .rbox로 빨간 손그림 테두리. 자막 프리셋 kozarie(극태·黄色 강조)와 세트",
             "css": """
body{background:#2f5b47 url('file://FRAME_PNG') no-repeat left top;background-size:100% auto;padding:10.4% 8.5% 22%;color:#222;font-size:38px}
h1{position:absolute;left:6.5vw;top:3.55vw;width:86vw;height:5.2vw;margin:0;padding:0 1vw;border:none;font-size:3.1vw;line-height:1.15;color:#1f3b63;background:none;white-space:nowrap;overflow:hidden;display:flex;align-items:center;letter-spacing:.02em} h1 small{color:#4a5a70;font-size:1.7vw;margin-left:1.2vw;white-space:nowrap}
table{font-size:36px} .key{font-size:42px} .note{font-size:28px} .steps li{font-size:38px}
b{text-decoration:underline wavy #3b82d6;text-decoration-thickness:5px;text-underline-offset:12px} th b,td b,.key b,.ov b{text-decoration:none}
.huge{font-size:92px;font-weight:bold;text-align:center;line-height:1.55;letter-spacing:.08em;margin:10px 0}
.huge b{text-decoration-thickness:6px;text-underline-offset:16px}
.rbox{display:inline-block;border:7px solid #b8312f;border-radius:10px;padding:0 38px;margin:6px 0}
th{background:#2f5b47;color:#fff;border:2px solid #2f5b47} td{border:2px solid #777}
td.hi{background:#ffe3e0;color:#b8312f} td.lo{background:#e3f1f4} tr.now td{background:#fff3b0}
.key{background:#fff8d6;border-left:12px solid #e0a800;color:#333}
.big{color:#b8312f}
.cover{padding-top:60px} .cover h2{color:#1f3b63;font-size:84px} .cover h3{color:#333} .cover p{color:#666}
.ill-right{width:460px}
"""},
 "chalk": {"label": "黒板 (녹색 칠판·흰 글자)", "font": "Zen丸ゴシック",
           "desc": "녹색 칠판에 흰 글자, 노란 분필 강조. 일러스트는 흰 테두리 사진처럼 붙음. 눈에 띄지만 표가 많으면 어두움",
           "css": """
body{background:#2e5e4e;color:#fff}
h1{color:#fff59d;border-bottom:4px dashed #fff} h1 small{color:#e0e0e0}
th{background:rgba(255,255,255,.18);color:#fff59d;border:2px solid rgba(255,255,255,.7)} td{border:2px solid rgba(255,255,255,.6)}
td.hi{background:rgba(255,213,79,.3);color:#ffe082} td.lo{background:rgba(255,255,255,.12)} tr.now td{background:rgba(255,213,79,.3);color:#fff}
.key{background:rgba(255,255,255,.12);border-left:14px solid #ffd54f;color:#fff}
.big{color:#ffab40} .note,.cover p{color:#cfd8dc}
.cover h2{color:#fff59d} .cover h3{color:#fff}
.ill-top img,.ill-right img,.ill-cover img{border-radius:14px;border:6px solid #fff}
"""},
}

def _frame_png():
    """黒板＋木枠＋白い紙＋水色の帯（1920×1080）。無ければ描く"""
    from PIL import Image, ImageDraw
    d_ = os.path.join(HERE, "out", "_style"); os.makedirs(d_, exist_ok=True); p = os.path.join(d_, "kokuban_frame2.png")
    if os.path.exists(p): return p
    im = Image.new("RGB", (1920, 1080), (47, 91, 71)); d = ImageDraw.Draw(im)
    for y in range(0, 1080, 3):                                              # 黒板のムラ
        d.line([0, y, 1920, y], fill=(44 + (y // 3) % 5, 88 + (y // 7) % 4, 68))
    d.rectangle([86, 50, 1834, 880], fill=(140, 92, 44))                       # 木枠
    d.rectangle([92, 56, 1828, 874], outline=(100, 62, 26), width=3)
    d.rectangle([104, 68, 1816, 862], fill=(255, 255, 255))                    # 紙
    d.rectangle([104, 68, 1816, 168], fill=(207, 236, 240))                    # 水色の帯（見出し用・高め）
    d.line([104, 168, 1816, 168], fill=(150, 200, 210), width=2)
    im.save(p); return p

def css(key):
    if key == "kokuban":
        return THEMES["kokuban"]["css"].replace("FRAME_PNG", _frame_png())
    return (THEMES.get(key or "navy") or THEMES["navy"])["css"]

def max_h(key):
    """本文を収める高さの上限（紙の枠があるテーマ）。無ければ None"""
    return (THEMES.get(key or "navy") or {}).get("max_h")

def font_for(key):
    return (THEMES.get(key or "navy") or THEMES["navy"])["font"]

DEMO_TITLE, DEMO_SUB = "科目別の配分｜300時間の内訳", "出題数と時間は比例させる"
DEMO_BODY = ("<table><tr><th>科目</th><th class='c'>出題数</th><th class='c'>目安の時間</th><th>ポイント</th></tr>"
             "<tr class='now'><td><b>宅建業法</b></td><td class='c'>20問</td><td class='c hi'><b>約100時間</b></td><td>満点近くを狙う科目。過去問の繰り返しが効く</td></tr>"
             "<tr><td><b>権利関係</b>（民法など）</td><td class='c'>14問</td><td class='c hi'><b>約100時間</b></td><td>時間がかかる。深追いせず<b>基本の型</b>で8〜9問</td></tr>"
             "<tr><td>法令上の制限</td><td class='c'>8問</td><td class='c'>約55時間</td><td>暗記中心。数字の表を作る</td></tr>"
             "<tr><td>税・その他</td><td class='c'>8問</td><td class='c lo'>約45時間</td><td>直前期にまとめて</td></tr></table>"
             "<div class='key'>宅建業法と権利関係で<b>全体の約7割</b>。後半は過去問に時間を寄せる</div>"
             "<p class='note'>※ 予備校の公表する目安。前提知識で増減します。</p>")
DEMO_COVER = ("<div class='cover'><h2>宅建に合格した人は<br>1日何時間勉強したのか</h2>"
              "<h3>合計300時間の内訳・科目別の配分・6か月／4か月／3か月のモデル計画</h3><p>※ 数字は予備校の公表値と合格者アンケートをもとにしています。</p></div>")

def sample(key, out, with_cover=True):
    """テーマの見本画像を out に書く（1920×1080 を2枚、横に並べて 1920 幅に縮小）"""
    import r8_goukaku as G, vkit as V, subs
    from PIL import Image
    old = V.SUB_STYLE
    V.SUB_STYLE = dict(subs.load_style(), slide_theme=key, slide_font=font_for(key))
    try:
        p1, _h = G.render(DEMO_BODY, DEMO_TITLE, DEMO_SUB, f"theme_{key}_a")
        ims = [Image.open(p1).convert("RGB").crop((0, 0, 1920, 1080))]
        if with_cover:
            p2, _h = G.render(DEMO_COVER, "", "", f"theme_{key}_b")
            ims.append(Image.open(p2).convert("RGB").crop((0, 0, 1920, 1080)))
    finally:
        V.SUB_STYLE = old
    w = 1920 // len(ims); h = int(1080 * w / 1920)
    canvas = Image.new("RGB", (1920, h), "#888")
    for i, im in enumerate(ims): canvas.paste(im.resize((w - 6, h - 6)), (i * w + 3, 3))
    canvas.save(out); return out

if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else "."
    for k in THEMES: print(sample(k, os.path.join(d, f"theme_{k}.png")))
