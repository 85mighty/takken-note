# -*- coding: utf-8 -*-
"""暗記ノート 動画 (16:9) — 各章のページが音声に合わせて下へスクロールする。

  python3 coaching/make_video.py --subject toshi            # static/video/toshi_note.mp4
  python3 coaching/make_video.py --subject kenki --only 3   # 第3章だけ (テスト用)

仕組み:
  1) static/docs/<key>_note.pdf の章ページを pdftoppm で幅 1920px の画像に
  2) pdfplumber で「1.」「2.」… の項目の縦位置を取る
  3) Google Cloud TTS (v1beta1, SSML <mark>) で章の音声を合成し、各項目を読み始める秒を取得
  4) ffmpeg の crop フィルタで、その秒にその項目が画面上 1/3 に来るよう滑らかにスクロール
  5) 章ごとの mp4 を連結
必要: ffmpeg, pdftoppm (poppler-utils), pdfplumber, Google TTS API キー (.google_api_key)
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import subjects  # noqa: E402
import make_audio_eleven  # noqa: E402
from make_audio_eleven import cfg_file  # noqa: E402
from make_audio_eleven import speakable  # noqa: E402
from make_audio_google import google_key, DEFAULT_VOICE  # noqa: E402

make_audio_eleven.READINGS.clear()

API = "https://texttospeech.googleapis.com/v1beta1/text:synthesize"
W, H, FPS = 1920, 1080, 30
FOCUS = 0.30          # 読んでいる項目を画面の上から 30% の位置に
TAIL = 1.2            # 章末の余白 (秒)


def chapter_lines(c):
    """台本の行: [title, meaning, item1..itemN, まとめ]"""
    title = c["title"].replace("　", "、").replace("――", "、").replace("―", "、").replace("・", "、")
    lines = [title + "。", speakable(c["meaning"]).rstrip("。") + "。"]
    for n, it in enumerate(c["items"], 1):
        body = speakable(it).rstrip("。")
        lines.append(f"{n}番、{body}" + ("" if body.endswith(("！", "？")) else "。"))
    lines.append("まとめ。" + speakable(c["one"]) + "。")
    return lines


def synth_with_marks(key, voice, rate, lines, mp3):
    """SSML で各行の前に <mark> を置き、読み始めの秒を返す。"""
    parts = ["<speak>"]
    for k, line in enumerate(lines):
        parts.append(f'<mark name="m{k}"/>{escape(line)}<break time="350ms"/>')
    parts.append("</speak>")
    body = json.dumps({"input": {"ssml": "".join(parts)},
                       "voice": {"languageCode": "ja-JP", "name": voice},
                       "audioConfig": {"audioEncoding": "MP3", "speakingRate": rate, "sampleRateHertz": 24000},
                       "enableTimePointing": ["SSML_MARK"]}).encode("utf-8")
    import time
    res = None
    for attempt in range(4):   # 一時的な "Failed to synthesize" に備えて再試行
        req = urllib.request.Request(f"{API}?key={key}", data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                res = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:600]
            if attempt == 3 or e.code in (401, 403):
                sys.exit(f"Google TTS エラー {e.code}: {msg}")
            print(f"  ※ Google TTS エラー {e.code} → {5 * (attempt + 1)} 秒後に再試行")
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 3:
                sys.exit(f"Google TTS 接続エラー: {e}")
            time.sleep(5 * (attempt + 1))
    with open(mp3, "wb") as f:
        f.write(base64.b64decode(res["audioContent"]))
    tp = {t["markName"]: float(t["timeSeconds"]) for t in res.get("timepoints", [])}
    return [tp.get(f"m{k}", 0.0) for k in range(len(lines))]


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def page_layout(pdf_path, page_no, scale):
    """ページ内の各行 (title, meaning, items..., まとめ) の縦位置 (px)。"""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        pg = pdf.pages[page_no]
        words = pg.extract_words()
        ph = pg.height
    items = sorted((int(w["text"][:-1]), w["top"]) for w in words if re.fullmatch(r"\d+\.", w["text"]) and w["x0"] < 80)
    title_top = min(w["top"] for w in words)
    meaning_top = min((w["top"] for w in words if w["top"] > title_top + 15), default=title_top)
    one_top = max((w["top"] for w in words if w["text"].startswith("一文")), default=ph - 60)
    ys = [title_top, meaning_top] + [t for _, t in items] + [one_top]
    return [y * scale for y in ys], ph * scale


def scroll_expr(times, ys, page_h, dur):
    """項目ごとの (秒, 位置) を折れ線でつなぐ ffmpeg の式。"""
    # ページ下の余白まで下げない: 「一文」の箱の少し下で止める
    maxy = max(0.0, min(page_h - H, ys[-1] + 230 - H))
    pts = [(0.0, 0.0)]
    for t, y in zip(times, ys):
        target = min(maxy, max(0.0, y - FOCUS * H))
        if t > pts[-1][0]:
            pts.append((t, max(target, pts[-1][1])))   # 戻らない (単調増加)
    pts.append((dur + 5, pts[-1][1]))
    expr = f"{pts[-1][1]:.1f}"
    for (t0, y0), (t1, y1) in reversed(list(zip(pts, pts[1:]))):
        seg = f"{y0:.1f}+({y1:.1f}-{y0:.1f})*(t-{t0:.3f})/{max(t1 - t0, 0.001):.3f}"
        expr = f"if(lt(t,{t1:.3f}),{seg},{expr})"
    return expr


def render_chapter(key, i, c, pdf_path, voice, rate, keyv, workdir, force=False):
    page = i  # 表紙が 0 ページ目なので 第i章 = ページ i
    out = os.path.join(workdir, f"{key}_{i:02d}.mp4")
    if not force and os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(pdf_path):
        print(f"{i:02d} 済み (再生成は --force)  {c['title']}")
        return out
    png = os.path.join(workdir, f"{key}_{i:02d}.png")
    subprocess.run(["pdftoppm", "-f", str(page + 1), "-l", str(page + 1), "-r", "232", "-png", "-singlefile",
                    pdf_path, png[:-4]], check=True)
    ident = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", png], capture_output=True, text=True).stdout.strip().split(",")
    pw, ph = int(ident[0]), int(ident[1])
    scale_fix = W / pw
    # 幅をぴったり 1920 に
    png2 = os.path.join(workdir, f"{key}_{i:02d}_w.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", png, "-vf", f"scale={W}:-2", png2], check=True)
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        pts_w = pdf.pages[page].width
    ys, page_h = page_layout(pdf_path, page, W / pts_w)
    page_h = int(round(ph * scale_fix))
    if page_h < H:  # 念のため (短いページ)
        png3 = os.path.join(workdir, f"{key}_{i:02d}_p.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", png2, "-vf", f"pad={W}:{H}:0:0:white", png3], check=True)
        png2, page_h = png3, H

    lines = chapter_lines(c)
    mp3 = os.path.join(workdir, f"{key}_{i:02d}.mp3")
    times = synth_with_marks(keyv, voice, rate, lines, mp3)
    dur = duration(mp3) + TAIL
    n = min(len(times), len(ys))
    expr = scroll_expr(times[:n], ys[:n], page_h, dur)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", png2, "-i", mp3,
                    "-filter_complex", f"[0:v]crop={W}:{H}:0:'{expr}',format=yuv420p[v];[1:a]apad=pad_dur={TAIL}[a]",
                    "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}", "-r", str(FPS),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-tune", "stillimage",
                    "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out], check=True)
    print(f"{i:02d} {dur:6.1f}s  {c['title']}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", default="toshi", choices=list(subjects.SUBJECTS))
    ap.add_argument("--voice", default=os.environ.get("GOOGLE_TTS_VOICE") or cfg_file(".google_voice") or DEFAULT_VOICE)
    ap.add_argument("--rate", type=float, default=1.0)
    ap.add_argument("--only", type=int)
    ap.add_argument("--force", action="store_true", help="作成済みの章も作り直す")
    ap.add_argument("--out", default=os.path.join(ROOT, "static", "video"))
    a = ap.parse_args()
    keyv = google_key()
    if not keyv:
        sys.exit("Google の API キーがありません:  echo 'AIza...' > .google_api_key")
    key, CH, name = a.subject, subjects.chapters(a.subject), subjects.name(a.subject)
    pdf_path = os.path.join(ROOT, "static", "docs", f"{key}_note.pdf")
    os.makedirs(a.out, exist_ok=True)
    work = os.path.join(a.out, f"work_{key}")
    os.makedirs(work, exist_ok=True)
    print(f"[{name}] 声: {a.voice}  → {a.out}")
    segs = []
    for i, c in enumerate(CH, 1):
        if a.only and a.only != i:
            continue
        segs.append(render_chapter(key, i, c, pdf_path, a.voice, a.rate, keyv, work, a.force))
    final = os.path.join(a.out, f"{key}_note{'_' + str(a.only) if a.only else ''}.mp4")
    if len(segs) == 1:
        os.replace(segs[0], final)
    else:
        lst = os.path.join(work, "list.txt")
        with open(lst, "w") as f:
            for s in segs:
                f.write(f"file '{os.path.abspath(s)}'\n")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                        "-movflags", "+faststart", final], check=True)
    print("完了:", final, f"{os.path.getsize(final) / 1e6:.1f} MB  {duration(final) / 60:.1f} 分")


if __name__ == "__main__":
    main()
