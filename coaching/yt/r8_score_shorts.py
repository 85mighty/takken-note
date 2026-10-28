# -*- coding: utf-8 -*-
"""自己採点の点数別ショート (31〜35点) 1080x1920
  python3 r8_score_shorts.py [--only 33]
  ショートの画面下 (タイトル・ボタン) と右端 (いいね等) に重ならないよう、内容は上〜中央、字幕は中段下に置く
"""
import argparse, html, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import vkit as V
from vkit import tts, dur, FPS
from weasyprint import HTML
from PIL import Image

SW, SH = 1080, 1920
SUB_Y = 1330                     # 字幕帯の上端
OUT = os.path.join(V.OUT, "score_shorts"); os.makedirs(OUT, exist_ok=True)
E = html.escape

# 各社予想 (10/25時点) との関係
S = {
 35: dict(label="35点以上", verdict="ほぼ安全圏", color="#c0392b",
          rows=[("TAC・日建・LEC・フォーサイト", "34点±1 → 上限ちょうど"), ("大原・大栄", "33・34点 → 上回る"), ("ユーキャン", "32点±1 → 上回る")],
          todo=["登録実務講習の日程を調べる（2年未満の人）", "本籍地・法務局・住民票の書類を準備"],
          say="宅建2026、自己採点35点以上の人へ。10月25日時点の各社予想は、いちばん高いところでも34点プラスマイナス1点。35点は全社の予想の上限以上で、ほぼ安全圏です。実務経験が2年未満の人は、登録実務講習の日程を今から調べておきましょう。12月から1月の開講分から埋まります。"),
 34: dict(label="34点", verdict="有力", color="#c0392b",
          rows=[("TAC・日建・LEC・フォーサイト", "34点±1 → 中心"), ("大原・大栄", "33・34点 → 範囲内"), ("住宅新報", "33点前後 → 上回る"), ("ユーキャン", "32点±1 → 上回る")],
          todo=["問33を1と答えた人は、33点として見直す", "登録実務講習の候補日を押さえておく"],
          say="宅建2026、自己採点34点の人へ。34点は、TAC、日建学院、LEC、フォーサイトの予想の中心で、大原と大栄の範囲にも入っています。過去5年、各社の予想の中心を実際の合格点が上回ったのは1回だけ。有力です。ただし、割れ問の問33を1と答えた人は、33点として見直してください。"),
 33: dict(label="33点", verdict="五分五分よりやや上", color="#b7791f",
          rows=[("大原・大栄・住宅新報", "33点が中心・範囲内"), ("TAC・日建・LEC・フォーサイト", "34点±1 → 下限"), ("ユーキャン", "32点±1 → 上限"), ("去年（令和7年度）", "実際の合格点が33点")],
          todo=["合格・不合格の両方に備える", "登録実務講習の候補日を押さえつつ、来年の計画も下書き"],
          say="宅建2026、自己採点33点の人へ。33点は、大原、大栄、住宅新報の予想の中心で、TACや日建学院の予想の下限、ユーキャンの上限です。全社の予想に入っている、数少ない点数のひとつ。そして去年の実際の合格点も33点でした。五分五分よりやや上。合格と不合格、両方に備えておきましょう。"),
 32: dict(label="32点", verdict="厳しいが可能性あり", color="#1a3d7c",
          rows=[("ユーキャン", "32点±1 → 中心"), ("アガルート（林講師）", "32点"), ("TAC・日建・LEC・フォーサイト", "34点±1 → 範囲外"), ("過去5年", "外れた6件中5件は『実際が低かった』")],
          todo=["分野別の得点を書き出しておく", "発表までは来年の準備も並行"],
          say="宅建2026、自己採点32点の人へ。32点は、ユーキャンの予想の中心で、アガルートの講師1人も32点としています。ただ、TACや日建学院など多くの会社の予想からは外れています。それでも、過去5年で予想が外れた6件のうち5件は、実際の合格点が予想より低かったケースです。厳しいですが、可能性は残っています。"),
 31: dict(label="31点", verdict="厳しい。来年の準備も", color="#1a3d7c",
          rows=[("ユーキャン", "32点±1 → 下限"), ("ほかの各社", "範囲外"), ("過去の最低", "平成27年度の31点"), ("今年の傾向", "個数10問・組合せ5問で難化")],
          todo=["分野別の得点と「あと何点」を記録", "来年は7月申込み・10月第3日曜日"],
          say="宅建2026、自己採点31点の人へ。31点は、ユーキャンの予想の下限で、ほかの会社の予想からは外れています。過去の最低は平成27年度の31点。今年は個数問題と組合せ問題が多く難化しましたが、厳しい位置です。発表は確認しつつ、分野別の得点を書き出して、来年への準備も始めておきましょう。"),
}
END = "詳しくは、合格点予想まとめ第2弾で。発表は11月25日、9時30分です。"

def page(sc):
    d = S[sc]
    rows = "".join(f"<tr><td>{E(a)}</td><td>{E(b)}</td></tr>" for a, b in d["rows"])
    todo = "".join(f"<li>{E(t)}</li>" for t in d["todo"])
    css = f"""@page {{ size: {SW/96*25.4:.1f}mm {SH/96*25.4:.1f}mm; margin: 0; }}
    body {{ margin:0; width:{SW}px; height:{SH}px; background:#fff; font-family:"Noto Sans CJK JP",sans-serif; color:#111; }}
    .top {{ background:#0f1b33; color:#fff; text-align:center; padding:70px 40px 34px; }}
    .top .t1 {{ font-size:40px; font-weight:bold; color:#ffd166; }}
    .top .t2 {{ font-size:46px; font-weight:bold; margin-top:8px; }}
    .score {{ text-align:center; margin:30px 0 0; }}
    .score .n {{ font-size:230px; font-weight:900; color:{d['color']}; line-height:1; }}
    .score .q {{ font-size:64px; font-weight:bold; margin-top:4px; }}
    .verdict {{ margin:26px 60px 0; background:{d['color']}; color:#fff; text-align:center; font-size:58px; font-weight:bold; border-radius:20px; padding:18px 10px; }}
    table {{ border-collapse:collapse; margin:30px 60px 0; width:calc(100% - 160px); font-size:33px; }}
    td {{ border-bottom:2px solid #ccd; padding:12px 10px; line-height:1.35; vertical-align:top; }}
    td:first-child {{ font-weight:bold; width:46%; color:#1a3d7c; }}
    .todo {{ margin:22px 60px 0 60px; padding:16px 24px 16px 60px; background:#fff3c4; border-left:12px solid #e0a800; font-size:33px; line-height:1.45; width:calc(100% - 260px); }}
    .todo li {{ margin:4px 0; }}
    .note {{ position:absolute; left:60px; right:160px; top:{SUB_Y + 200}px; font-size:26px; color:#666; line-height:1.4; }}"""
    body = f"""<div class='top'><div class='t1'>宅建2026 自己採点</div><div class='t2'>合格点予想（10/25時点）と比べると</div></div>
    <div class='score'><div class='n'>{E(d['label'])}</div><div class='q'>は受かる？</div></div>
    <div class='verdict'>{E(d['verdict'])}</div>
    <table>{rows}</table>
    <ul class='todo'>{todo}</ul>
    <div class='note'>※ 各社予想は10/25時点。5問免除の人は5点引いて読み替え。正式な合格点は11/25（水）9:30発表</div>"""
    pdf = os.path.join(OUT, f"sc{sc}.pdf"); png = os.path.join(OUT, f"sc{sc}.png")
    HTML(string=f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>").write_pdf(pdf)
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "96", "-png", "-singlefile", pdf, png[:-4]], check=True)
    Image.open(png).convert("RGB").resize((SW, SH)).save(png)
    return png

def build(sc):
    d = S[sc]
    png = page(sc)
    speech = d["say"] + END
    sents = V.split_sentences(speech)
    mp3 = os.path.join(OUT, f"sc{sc}.mp3")
    tp = tts(V.ssml_sentences(sents, pause_ms=250), mp3, ssml=True, rate=1.12)
    total = dur(mp3) + 0.8
    bands = [V.band_png(s, f"sc{sc}_b{i}", OUT, width=SW, font=50) for i, s in enumerate(sents)]
    sp = V.spans(tp, len(sents), total)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", png, "-i", mp3]
    for b in bands: cmd += ["-loop", "1", "-framerate", str(FPS), "-i", b]
    fc = "[0:v]null[v0]"
    for i, (t0, t1) in enumerate(sp):
        fc += f";[v{i}][{i+2}:v]overlay=0:{SUB_Y}:enable='between(t,{t0:.3f},{t1:.3f})'[v{i+1}]"
    fc += f";[v{len(sp)}]format=yuv420p[v];[1:a]apad=whole_dur={total:.2f}[a]"
    tmp = os.path.join(OUT, f"sc{sc}_nobgm.mp4")
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-tune", "stillimage", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", tmp]
    subprocess.run(cmd, check=True)
    final = os.path.join(OUT, f"ショート_宅建2026_自己採点{d['label'].replace('以上','以上')}.mp4")
    V.add_bgm(tmp, final)
    print(f"{d['label']}: {total:.0f}s → {os.path.basename(final)}", flush=True)
    return final

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--only", type=int); a = ap.parse_args()
    for sc in (35, 34, 33, 32, 31):
        if a.only and a.only != sc: continue
        build(sc)
