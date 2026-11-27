# -*- coding: utf-8 -*-
"""科目別ロング (1920x1080) と ショート (1080x1920)
 流れ: 「問題N」＋問題文を速めに読み上げ → 一時停止の案内 → 正解と4肢すべての○×理由を読み上げ
  python3 r8_subject.py --subject kenri [--only 3]     kenri(1-14) horei(15-22) zei(23-25,46-50) gyoho(26-45)
  python3 r8_subject.py --shorts [--only 3]
"""
import argparse, os, subprocess, sys
from xml.sax.saxutils import escape
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import vkit as V
from vkit import Q, esc, tts, dur, scroll_expr, speakable, W, H, FPS
from r8_exp import EXP
from weasyprint import HTML
from PIL import Image, ImageOps

SUBJ = {
 "kenri": ("権利関係", list(range(1, 15))),
 "horei": ("法令上の制限", list(range(15, 23))),
 "zei":   ("税・その他", [23, 24, 25, 46, 47, 48, 49, 50]),
 "gyoho": ("宅建業法", list(range(26, 46))),
}
OUT = os.path.join(V.OUT, "subj"); os.makedirs(OUT, exist_ok=True)
SOUT = os.path.join(V.OUT, "shorts"); os.makedirs(SOUT, exist_ok=True)
Q_RATE = 1.22      # 問題文の読み上げ速度
A_RATE = 1.08      # 解説の読み上げ速度

def page_css(width, font, pad):
    return f"""
@page {{ size: {width/96*25.4:.1f}mm 3000mm; margin: 0; }}
body {{ width: {width}px; box-sizing: border-box; margin: 0; padding: {pad}px {pad}px 240px; font-family: "Noto Sans CJK JP", sans-serif; font-size: {font}px; line-height: 1.6; color: #111; background: #fff; }}
.qh {{ font-weight: bold; font-size: {font+2}px; margin-bottom: 14px; }}
.qn {{ background: #1a3d7c; color: #fff; padding: 2px 18px; border-radius: 8px; margin-right: 16px; font-size: {font-2}px; }}
.sub {{ margin: 6px 0 6px 30px; }}
.ch {{ display: flex; margin: 8px 0; }}
.ch .n {{ width: {int(font*1.7)}px; flex-shrink: 0; font-weight: bold; }}
.pause {{ margin-top: 40px; background: #fff3c4; border: 4px solid #e0a800; border-radius: 16px; padding: 20px 36px; font-size: {font+2}px; font-weight: bold; line-height: 1.5; }}
.pause small {{ display: block; font-size: {font-6}px; font-weight: normal; color: #555; margin-top: 6px; }}
.a {{ margin-top: 40px; border: 4px solid #c0392b; border-radius: 16px; padding: 24px 36px; background: #fff8f6; }}
.ah {{ font-size: {font+6}px; font-weight: bold; margin-bottom: 14px; }}
.ans {{ color: #c0392b; font-size: {font+26}px; font-weight: bold; margin: 0 20px; }}
.ex {{ display: flex; margin: 10px 0; font-size: {font-2}px; line-height: 1.6; }}
.ex .l {{ width: {int(font*1.6)}px; flex-shrink: 0; font-weight: bold; }}
.ex .m {{ width: {int(font*1.4)}px; flex-shrink: 0; font-weight: bold; }}
.ex .m.o {{ color: #c0392b; }} .ex .m.x {{ color: #1a3d7c; }}
.now {{ background: #fff3b0; box-shadow: 0 0 0 8px #fff3b0; border-radius: 6px; }}
.ex.now {{ box-shadow: 0 0 0 10px #fff3b0; }}
.hint {{ color: #555; font-size: {font-6}px; margin-bottom: 24px; }}
.title {{ text-align: center; padding-top: 330px; }}
.title h1 {{ font-size: 80px; margin: 0 0 30px; color: #1a3d7c; }}
.title h2 {{ font-size: 52px; margin: 0 0 60px; font-weight: normal; }}
.title p {{ font-size: 34px; color: #555; }}
"""

def render(body, name, width, font, pad, outdir, minh):
    pdf = os.path.join(outdir, name + ".pdf"); png = os.path.join(outdir, name + ".png")
    HTML(string=f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{page_css(width, font, pad)}</style></head><body>{body}</body></html>").write_pdf(pdf)
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "96", "-png", "-singlefile", pdf, png[:-4]], check=True)
    im = Image.open(png).convert("RGB")
    if im.size[0] != width: im = im.resize((width, int(im.size[1] * width / im.size[0])))
    bbox = ImageOps.invert(im.convert("L")).point(lambda v: 255 if v > 55 else 0).getbbox()
    bottom = max(minh, min(im.size[1], (bbox[3] + 140) if bbox else minh))
    im = im.crop((0, 0, width, bottom)); im.save(png)
    return png, bottom, pdf

def q_html(q, hint, hl=False):
    cls = 'qh now' if (hl and V.HIGHLIGHT) else 'qh'
    b = (f"<div class='hint'>{esc(hint)}</div>" if hint else "") + f"<div class='{cls}'><span class='qn'>問題{q['n']}</span>{esc(q['stem'])}</div>"
    for s in q["subs"]: b += f"<div class='sub'>{esc(s)}</div>"
    for i, c in enumerate(q["choices"], 1): b += f"<div class='ch'><span class='n'>{i}</span><span>{esc(c)}</span></div>"
    return b

def pause_html(shorts=False):
    if shorts:
        return "<div class='pause'>▌▌ 画面をタップして一時停止 → 解いてみてね<small>そのまま見ると、すぐ正解と解説が出ます</small></div>"
    return "<div class='pause'>▌▌ ここで一時停止して、問題を解いてみてください<small>すぐに答えを見たい方は、そのままどうぞ。正解と解説が続きます</small></div>"

def a_html(q, hl=None):
    a = "保留" if q["answer"] is None else str(q["answer"])
    b = f"<div class='a'><div class='ah'>正解<span class='ans'>{a}</span></div>"
    for k, (lab, mk, why) in enumerate(EXP[q["n"]]):
        cls = "o" if mk == "○" else "x"
        row = "ex now" if hl == k else "ex"
        b += f"<div class='{row}'><span class='l'>{esc(lab)}</span><span class='m {cls}'>{mk}</span><span>{esc(why)}</span></div>"
    return b + "</div>"

def spk(s):
    return speakable(s).replace("○", "まる").replace("×", "ばつ").replace("？", "はてな")

def q_ssml(q):
    """問題文（設問）だけ読み上げる。肢は読まない。"""
    return "<speak>" + f'<mark name="s"/>{escape(spk("問題" + str(q["n"]) + "。" + q["stem"]))}<break time="300ms"/>' + "</speak>"

def read_sec(q):
    """肢を黙読する時間"""
    n = sum(map(len, q["subs"])) + sum(map(len, q["choices"]))
    return max(6.0, min(22.0, n * 0.045))

def a_ssml(q):
    a = "保留" if q["answer"] is None else str(q["answer"])
    parts = [f'<mark name="a"/>正解は、{a}。<break time="500ms"/>']
    for k, (lab, mk, why) in enumerate(EXP[q["n"]]):
        m = {"○": "まる", "×": "ばつ"}.get(mk, "保留")
        parts.append(f'<mark name="e{k}"/>{escape(lab)}は、{m}。{escape(spk(why))}<break time="450ms"/>')
    return "<speak>" + "".join(parts) + "</speak>"

def tops(pdf, scale, labels_prefix):
    """ページ内の各行の縦位置(px)。labels_prefix: 行頭の文字列のリスト (順序どおりに出現する前提)"""
    import pdfplumber
    with pdfplumber.open(pdf) as p:
        ws = sorted(p.pages[0].extract_words(), key=lambda w: (w["top"], w["x0"]))
    out = []; i = 0
    for w in ws:
        if i < len(labels_prefix) and w["text"].startswith(labels_prefix[i]) and w["x0"] < 200:
            out.append(w["top"] * scale); i += 1
    while len(out) < len(labels_prefix): out.append(out[-1] if out else 0)
    return out

def q_marks_pts(q, tp, ys_choices, win_h, page_h):
    """肢の読み上げ時刻に、その肢が画面の上1/3に来るように"""
    pts = []
    for i in range(1, len(q["choices"]) + 1):
        t = tp.get(f"c{i}")
        if t is None: continue
        pts.append((t, ys_choices[i - 1] - int(win_h * 0.30)))
    return pts

# ---------------- 共通: 1問ぶんの3セグメント ----------------
def build_question(q, hint, width, font, pad, outdir, win_h, enc, shorts):
    name = f"{'s' if shorts else 'l'}{q['n']:02d}"
    pfx_choices = [f"{i}" for i in range(1, len(q["choices"]) + 1)]
    # 1) 問題ページ（読み上げ）
    png1, h1, pdf1 = render(q_html(q, hint, hl=True), name + "_q", width, font, pad, outdir, win_h)
    mp3q = os.path.join(outdir, name + "_q.mp3"); tts(q_ssml(q), mp3q, ssml=True, rate=Q_RATE)
    tq = dur(mp3q)
    t1 = tq + 0.3          # 設問を読んだらすぐ次へ
    pts = []
    o1 = os.path.join(outdir, name + "_1.mp4"); enc([(png1, t1)], mp3q, scroll_expr(pts, max(0, h1 - win_h), t1), t1, o1)
    # 2) 一時停止の案内（問題＋黄色バナー）
    png2, h2, pdf2 = render(q_html(q, hint) + pause_html(shorts), name + "_p", width, font, pad, outdir, win_h)
    mp3p0 = os.path.join(outdir, name + "_p0.mp3"); mp3p = os.path.join(outdir, name + "_p.mp3")
    tts("画面をタップして一時停止し、解いてみてください。そのまま見ると、すぐ正解と解説です。" if shorts else
        "ここで一時停止して、問題を解いてみてください。すぐに答えを見たい方は、そのままどうぞ。", mp3p0, rate=1.05)
    with_ding(mp3p0, mp3p)
    # 効果音＋案内のあと、肢を黙読する時間をかけてゆっくり一番下（バナー）まで
    t2 = max(dur(mp3p) + 2.0, read_sec(q) + 1.0)
    pts2 = [(0.6, 0), (t2 - 0.6, h2 - win_h)] if h2 > win_h else []
    o2 = os.path.join(outdir, name + "_2.mp4"); enc([(png2, t2)], mp3p, scroll_expr(pts2, max(0, h2 - win_h), t2), t2, o2)
    # 3) 正解＋全肢の解説
    png3, h3, pdf3 = render(q_html(q, hint) + pause_html(shorts) + a_html(q), name + "_a", width, font, pad, outdir, win_h)
    mp3a = os.path.join(outdir, name + "_a.mp3"); tpa = tts(a_ssml(q), mp3a, ssml=True, rate=A_RATE)
    labs = ["正解"] + [lab for lab, _, _ in EXP[q["n"]]]
    ya = tops(pdf3, 96 / 72, labs)
    t3 = dur(mp3a) + 1.5
    pts3 = [(0.0, max(0, h2 - win_h)), (0.9, ya[0] - 90)]
    for k in range(len(EXP[q["n"]])):
        t = tpa.get(f"e{k}")
        if t is not None: pts3.append((t, ya[k + 1] - int(win_h * 0.28)))
    K = len(EXP[q["n"]])
    if V.HIGHLIGHT and all(tpa.get(f"e{k}") is not None for k in range(K)):
        variants = [png3] + [render(q_html(q, hint) + pause_html(shorts) + a_html(q, hl=k), f"{name}_a{k}", width, font, pad, outdir, win_h)[0] for k in range(K)]
        h3 = V.unify_heights(variants)
        ts = [tpa[f"e{k}"] for k in range(K)] + [t3]
        states = [(variants[0], ts[0])] + [(variants[k + 1], ts[k + 1] - ts[k]) for k in range(K)]
    else:
        states = [(png3, t3)]
    o3 = os.path.join(outdir, name + "_3.mp4"); enc(states, mp3a, scroll_expr(pts3, max(0, h3 - win_h), t3), t3, o3)
    print(f"{'short' if shorts else 'long'} 問題{q['n']}: 読{t1:.0f}s 停{t2:.0f}s 解{t3:.0f}s", flush=True)
    return [o1, o2, o3]

DING = os.path.join(V.OUT, "ding.wav")
def make_ding():
    if os.path.exists(DING): return
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "sine=frequency=1046:duration=0.35",
                    "-f", "lavfi", "-i", "sine=frequency=1318:duration=0.5",
                    "-filter_complex", "[0:a]afade=t=out:st=0.15:d=0.2,volume=0.35[a];[1:a]afade=t=out:st=0.1:d=0.4,volume=0.35[b];[a][b]concat=n=2:v=0:a=1,aresample=24000[o]",
                    "-map", "[o]", "-ac", "1", DING], check=True)

def with_ding(mp3, out):
    """効果音 → 0.25秒の間 → 案内音声"""
    make_ding()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", DING, "-i", mp3,
                    "-filter_complex", "[0:a]apad=pad_dur=0.25[d];[d][1:a]concat=n=2:v=0:a=1[o]", "-map", "[o]", "-ac", "1", "-ar", "24000", out], check=True)
    return out

def enc_long(states, mp3, expr, total, out):
    V.encode_states(states, mp3, expr, total, out)

# ---------------- 科目別ロング ----------------
def build_subject(key, only=None):
    name, nums = SUBJ[key]
    segs = []
    if not only:
        segs.append(V.card(f"title_{key}", "2026年（令和8年度）宅建士試験", f"{name}　全問 解答・解説",
                           "問題を読み上げ → 一時停止して解く → 正解と4つの肢すべての解説。※独自解答", 7,
                           f"2026年、令和8年度、宅地建物取引士試験。{name}の全問を、1問ずつ解説します。問題の読み上げのあと、一時停止して解いてみてください。そのまま見ると、正解と、すべての肢の解説が続きます。", OUT))
    for i, n in enumerate(nums, 1):
        if only and only != n: continue
        q = next(x for x in Q if x["n"] == n)
        segs += build_question(q, f"令和8年度 宅建士試験　{name}　{i}/{len(nums)}", W, 36, 110, OUT, H, enc_long, False)
    if not only:
        segs.append(V.card(f"end_{key}", "お疲れさまでした", "", "※ 正解は独自の見解です。公式の正答をご確認ください。", 5,
                           "お疲れさまでした。正解は独自の見解です。公式の正答もご確認ください。", OUT))
    if only:
        final = os.path.join(OUT, f"R8_{key}_q{only}.mp4"); V.concat(segs, final)
        print("完了:", final, f"{os.path.getsize(final)/1e6:.1f}MB {dur(final)/60:.1f}分", flush=True); return
    label = {"kenri": "権利関係_問題1-14", "horei": "法令上の制限_問題15-22", "zei": "税その他_問題23-25_46-50", "gyoho": "宅建業法_問題26-45"}[key]
    lim = float(os.environ.get("YT_PART_MB", "27"))          # 0 なら分割しない (1本の高画質ファイル)
    parts = V.split_parts(segs, limit_mb=lim) if lim > 0 else [segs]
    for i, p in enumerate(parts, 1):
        final = os.path.join(OUT, f"令和8年_宅建_{label}" + (f"_part{i}" if len(parts) > 1 else "") + ".mp4")
        V.concat(p, final)
        print("完了:", final, f"{os.path.getsize(final)/1e6:.1f}MB {dur(final)/60:.1f}分", flush=True)

# ---------------- ショート ----------------
SW, SH = 1080, 1920
WIN_Y, WIN_H = 230, 1530
def shorts_frame(subj_name, n, name):
    css = f"""body{{width:{SW}px;height:{SH}px;margin:0;background:#0f1b33;font-family:"Noto Sans CJK JP",sans-serif;color:#fff;position:relative}}
    .top{{position:absolute;top:0;left:0;width:{SW}px;height:{WIN_Y}px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}}
    .t1{{font-size:44px;font-weight:bold;line-height:1.25}}.t2{{font-size:50px;font-weight:bold;color:#ffd166;margin-top:6px}}.t2 span{{display:inline-block;background:#c0392b;color:#fff;font-size:44px;padding:0 26px;border-radius:30px;margin-left:18px;vertical-align:middle}}
    .bot{{position:absolute;top:{WIN_Y+WIN_H}px;left:0;width:{SW}px;height:{SH-WIN_Y-WIN_H}px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}}
    .b1{{font-size:32px;color:#cfd8ea}}"""
    body = f"<div class='top'><div class='t1'>令和8年 宅建士試験</div><div class='t2'>{esc(subj_name)}　解説<span>問題{n}</span></div></div><div class='bot'><div class='b1'>タップで一時停止 → 解いてから答え合わせ　※独自解答</div></div>"
    pdf = os.path.join(SOUT, name + "_bg.pdf"); png = os.path.join(SOUT, name + "_bg.png")
    HTML(string=f"<html><head><meta charset='utf-8'><style>@page{{size:{SW/96*25.4:.1f}mm {SH/96*25.4:.1f}mm;margin:0}}{css}</style></head><body>{body}</body></html>").write_pdf(pdf)
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "96", "-png", "-singlefile", pdf, png[:-4]], check=True)
    Image.open(png).convert("RGB").resize((SW, SH)).save(png); return png

def short_question(q, subj_name):
    name = f"s{q['n']:02d}"
    bg = shorts_frame(subj_name, q["n"], name)
    def enc(states, mp3, expr, total, out):
        V.encode_states(states, mp3, expr, total, out, win_w=SW, win_h=WIN_H, bg=bg, win_y=WIN_Y)
    segs = build_question(q, "", SW, 38, 44, SOUT, WIN_H, enc, True)
    final = os.path.join(SOUT, f"短編_問題{q['n']:02d}_{subj_name}.mp4")
    V.concat(segs, final)
    print(f"  → {os.path.basename(final)} {dur(final):.0f}s", flush=True)
    return final

def subj_of(n):
    for k, (nm, nums) in SUBJ.items():
        if n in nums: return nm
    return ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", choices=list(SUBJ)); ap.add_argument("--shorts", action="store_true"); ap.add_argument("--only", type=int)
    a = ap.parse_args()
    if a.shorts:
        for q in Q:
            if a.only and q["n"] != a.only: continue
            short_question(q, subj_of(q["n"]))
    else:
        build_subject(a.subject, a.only)

if __name__ == "__main__":
    main()
