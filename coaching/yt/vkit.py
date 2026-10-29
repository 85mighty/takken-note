# -*- coding: utf-8 -*-
"""共通ヘルパー: TTS / ffmpeg スクロール動画化 / タイトルカード"""
import base64, html, json, os, subprocess, sys, time, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
from r8_q import Q
import make_audio_eleven; make_audio_eleven.READINGS.clear()
from make_audio import speakable
from weasyprint import HTML
from PIL import Image, ImageOps

W, H, FPS = 1920, 1080, 30
VOICE = "ja-JP-Neural2-D"
KEY = os.environ.get("GOOGLE_TTS_API_KEY", "")
API = "https://texttospeech.googleapis.com/v1beta1/text:synthesize"
OUT = os.environ.get("YT_OUT", os.path.join(HERE, "out")); os.makedirs(OUT, exist_ok=True)
BGM_DIR = os.path.join(HERE, "bgm")
BGM_DB = float(os.environ.get("YT_BGM_DB", "-22"))   # BGM の音量 (dBFS 相対)。0 以上で無効
HIGHLIGHT = os.environ.get("YT_HIGHLIGHT", "1") != "0"

CSS = """
@page { size: 508mm 2000mm; margin: 0; }
body { width: 1920px; box-sizing: border-box; margin: 0; padding: 40px 110px 200px; font-family: "Noto Sans CJK JP", sans-serif; font-size: 36px; line-height: 1.6; color: #111; background: #fff; }
.title { text-align: center; padding-top: 330px; }
.title h1 { font-size: 80px; margin: 0 0 30px; color: #1a3d7c; }
.title h2 { font-size: 52px; margin: 0 0 60px; font-weight: normal; }
.title p { font-size: 34px; color: #555; }
"""
def esc(s): return html.escape(s)

def render_png(body, name, outdir=None):
    outdir = outdir or OUT
    pdf = os.path.join(outdir, name + ".pdf"); png = os.path.join(outdir, name + ".png")
    HTML(string=f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>").write_pdf(pdf)
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "96", "-png", "-singlefile", pdf, png[:-4]], check=True)
    im = Image.open(png).convert("RGB")
    if im.size[0] != W: im = im.resize((W, int(im.size[1] * W / im.size[0])))
    bbox = ImageOps.invert(im.convert("L")).point(lambda v: 255 if v > 55 else 0).getbbox()
    bottom = max(H, min(im.size[1], (bbox[3] + 160) if bbox else H))
    im = im.crop((0, 0, W, bottom)); im.save(png)
    return png, bottom, pdf

READ = [("宅地建物取引士証","たくちたてものとりひきししょう"),("宅地建物取引士","たくちたてものとりひきし"),
        ("宅建士証","たっけんししょう"),("宅建士","たっけんし"),("宅建業法","たっけんぎょうほう"),("宅建業者","たっけんぎょうしゃ"),
        ("宅建業","たっけんぎょう"),("宅建試験","たっけんしけん"),("宅建","たっけん")]
def fix_read(s):
    for a, b in READ: s = s.replace(a, b)
    return s

def tts(text_or_ssml, mp3, ssml=False, rate=1.0):
    text_or_ssml = fix_read(text_or_ssml)
    inp = {"ssml": text_or_ssml} if ssml else {"text": text_or_ssml}
    body = json.dumps({"input": inp, "voice": {"languageCode": "ja-JP", "name": VOICE},
                       "audioConfig": {"audioEncoding": "MP3", "speakingRate": rate, "sampleRateHertz": 24000},
                       "enableTimePointing": ["SSML_MARK"]}).encode()
    for attempt in range(4):
        try:
            req = urllib.request.Request(f"{API}?key={KEY}", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r: res = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:400]
            if attempt == 3 or e.code in (401, 403): sys.exit(f"TTS error {e.code}: {msg}")
            time.sleep(5 * (attempt + 1))
    open(mp3, "wb").write(base64.b64decode(res["audioContent"]))
    return {t["markName"]: float(t["timeSeconds"]) for t in res.get("timepoints", [])}

def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip())

def scroll_expr(pts, maxy, total):
    pts = [(0.0, 0.0)] + [(t, min(maxy, max(0.0, y))) for t, y in pts]
    fixed = []
    for t, y in pts:
        if fixed and t <= fixed[-1][0]: continue
        y = max(y, fixed[-1][1]) if fixed else y
        fixed.append((t, y))
    fixed.append((total + 5, fixed[-1][1]))
    expr = f"{fixed[-1][1]:.1f}"
    for (t0, y0), (t1, y1) in reversed(list(zip(fixed, fixed[1:]))):
        expr = f"if(lt(t,{t1:.3f}),{y0:.1f}+({y1:.1f}-{y0:.1f})*(t-{t0:.3f})/{max(t1-t0,0.001):.3f},{expr})"
    return expr

def encode(png, page_h, mp3, expr, total, out):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", png, "-i", mp3,
                    "-filter_complex", f"[0:v]crop={W}:{H}:0:'{expr}',format=yuv420p[v];[1:a]apad=whole_dur={total:.2f}[a]",
                    "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-r", str(FPS),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-tune", "stillimage",
                    "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out], check=True)

def card(name, title, sub, note, sec, speech, outdir=None):
    outdir = outdir or OUT
    body = f"<div class='title'><h1>{esc(title)}</h1><h2>{esc(sub)}</h2><p>{esc(note)}</p></div>"
    png, h, _ = render_png(body, name, outdir)
    mp3 = os.path.join(outdir, name + ".mp3"); tts(speech, mp3)
    total = max(sec, dur(mp3) + 1.0)
    out = os.path.join(outdir, name + ".mp4"); encode(png, h, mp3, "0", total, out); return out


# ---------------- 文単位の読み上げ (字幕ハイライト用) ----------------
import re
def split_sentences(text):
    """「。」「！」「？」で区切る。短すぎる断片は前と結合。"""
    parts = [p for p in re.split(r"(?<=[。！？!?])\s*", text.strip()) if p]
    out = []
    for p in parts:
        if out and len(p) < 8: out[-1] += p
        else: out.append(p)
    return out

def ssml_sentences(sents, pause_ms=350):
    body = "".join(f'<mark name="s{i}"/>{html.escape(s)}<break time="{pause_ms}ms"/>' for i, s in enumerate(sents))
    return "<speak>" + body + "</speak>"

def spans(tp, n, total):
    """mark s0..s{n-1} の時刻 → [(t0,t1),...]"""
    ts = [tp.get(f"s{i}", 0.0) for i in range(n)]
    return [(ts[i], ts[i + 1] if i + 1 < n else total) for i in range(n)]

# ---------------- 字幕バンド (スライド動画の下部に、いま読んでいる文を表示) ----------------
BAND = 170
SUB_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
def band_png(text, name, outdir, width=W, font=46):
    """映画字幕風: 透明背景に白文字＋黒フチ＋影。帯は無し。最大2行、収まらなければ縮小"""
    from PIL import ImageDraw, ImageFont
    png = os.path.join(outdir, name + ".png")
    maxw = width - 2 * 120
    def wrap(fnt):
        lines, cur = [], ""
        for ch in text:
            if fnt.getlength(cur + ch) > maxw and cur:
                lines.append(cur); cur = ch
            else: cur += ch
        if cur: lines.append(cur)
        return lines
    size = font
    while True:
        fnt = ImageFont.truetype(SUB_FONT, size, index=0)
        lines = wrap(fnt)
        if len(lines) <= 2 or size <= 32: break
        size -= 4
    im = Image.new("RGBA", (width, BAND), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lh = int(size * 1.35); total_h = lh * len(lines); y = (BAND - total_h) // 2 + 4
    for ln in lines:
        w = fnt.getlength(ln); x = (width - w) / 2
        d.text((x + 3, y + 3), ln, font=fnt, fill=(0, 0, 0, 150), stroke_width=4, stroke_fill=(0, 0, 0, 150))   # 影
        d.text((x, y), ln, font=fnt, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0, 255))     # 本体
        y += lh
    im.save(png); return png

SUB_STYLE = None   # spec ごとの字幕スタイル上書き（build_spec が設定）

def encode_subtitled(png, mp3, expr, total, sents, tp, out, outdir, name, width=W, height=H):
    """スクロール動画 + 字幕。字幕は文を自然な位置で区切り（subs.chunk）、1枚ずつ切り替える。
    字幕は1本の映像トラック（concat）にまとめて重ねる → 画像を何枚重ねても速い"""
    import subs
    if not HIGHLIGHT or not sents:
        return encode(png, None, mp3, expr, total, out)
    st = subs.load_style(SUB_STYLE)
    items = subs.timed_chunks(sents, spans(tp, len(sents), total), int(st.get("max_chars", 20)))
    bh = subs.band_height(st); y = height - int(st.get("bottom", 56)) - bh
    blank = os.path.join(outdir, f"_blank_{width}x{bh}.png")
    if not os.path.exists(blank): Image.new("RGBA", (width, bh), (0, 0, 0, 0)).save(blank)
    entries, t = [], 0.0
    for k, (text, t0, t1) in enumerate(items):
        if t0 > t + 0.01: entries.append((blank, t0 - t))
        entries.append((subs.render(text, os.path.join(outdir, f"{name}_c{k}.png"), width, st), t1 - t0)); t = t1
    if total > t + 0.01: entries.append((blank, total - t))
    lst = os.path.join(outdir, f"{name}_subs.txt")
    with open(lst, "w") as f:
        for p_, d_ in entries: f.write(f"file '{os.path.abspath(p_)}'\nduration {max(d_, 0.04):.3f}\n")
        f.write(f"file '{os.path.abspath(entries[-1][0])}'\n")
    fc = (f"[0:v]fps={FPS},crop={width}:{height}:0:'{expr}'[bg];[2:v]fps={FPS},format=rgba[sub];"
          f"[bg][sub]overlay=0:{y}:eof_action=pass,format=yuv420p[v];[1:a]apad=whole_dur={total:.2f}[a]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "2", "-i", png, "-i", mp3,
           "-f", "concat", "-safe", "0", "-i", lst, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
           "-t", f"{total:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-tune", "stillimage",
           "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)

# ---------------- 画面内ハイライト (問題動画: 読んでいる肢の行を黄色に) ----------------
def unify_heights(pngs):
    ims = [Image.open(p).convert("RGB") for p in pngs]
    hmax = max(im.size[1] for im in ims)
    for p, im in zip(pngs, ims):
        if im.size[1] != hmax:
            bg = Image.new("RGB", (im.size[0], hmax), "white"); bg.paste(im, (0, 0)); bg.save(p)
    return hmax

def states_list(states, path):
    """concat demuxer 用 (png, 秒) のリスト"""
    with open(path, "w") as f:
        for png, d in states: f.write(f"file '{png}'\nduration {max(d, 0.04):.3f}\n")
        f.write(f"file '{states[-1][0]}'\n")
    return path

def encode_states(states, mp3, expr, total, out, win_w=W, win_h=H, bg=None, win_y=0):
    """複数の静止画を時刻で切り替えながらスクロール (bg があればショート用に枠へ重ねる)"""
    lst = states_list(states, out + ".states.txt")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", mp3]
    if bg:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-i", bg]
        fc = f"[0:v]fps={FPS},crop={win_w}:{win_h}:0:'{expr}'[p];[2:v][p]overlay=0:{win_y},format=yuv420p[v];[1:a]apad=whole_dur={total:.2f}[a]"
    else:
        fc = f"[0:v]fps={FPS},crop={win_w}:{win_h}:0:'{expr}',format=yuv420p[v];[1:a]apad=whole_dur={total:.2f}[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)

# ---------------- BGM ----------------
def find_bgm():
    if os.environ.get("YT_BGM"): return os.environ["YT_BGM"]
    if os.path.isdir(BGM_DIR):
        for f in sorted(os.listdir(BGM_DIR)):
            if f.lower().endswith((".mp3", ".wav", ".m4a", ".ogg", ".flac")) and not f.startswith("_"): return os.path.join(BGM_DIR, f)
    return None

def make_pad(path):
    """BGM ファイルが無いときの仮BGM: 静かなパッド (C△7)。本番は bgm/ に好きな曲を置く"""
    expr = "0.22*sin(2*PI*130.81*t)*(0.6+0.4*sin(2*PI*t/11))+0.18*sin(2*PI*164.81*t)*(0.6+0.4*sin(2*PI*t/13+1))+0.18*sin(2*PI*196*t)*(0.6+0.4*sin(2*PI*t/9+2))+0.14*sin(2*PI*246.94*t)*(0.6+0.4*sin(2*PI*t/17+3))+0.10*sin(2*PI*261.63*t)*(0.6+0.4*sin(2*PI*t/7+4))"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d=90",
                    "-af", "lowpass=f=900,afade=t=in:d=3,afade=t=out:st=87:d=3", "-ac", "2", path], check=True)
    return path

def add_bgm(video, out, bgm=None, db=None):
    """完成動画に BGM を重ねる。ナレーション中は自動で音量を下げる (ダッキング)。映像は再エンコードしない"""
    db = BGM_DB if db is None else db
    bgm = bgm or find_bgm()
    if db >= 0: 
        if video != out: os.replace(video, out)
        return out
    if bgm == "pad":
        os.makedirs(BGM_DIR, exist_ok=True); bgm = make_pad(os.path.join(BGM_DIR, "_pad_placeholder.wav"))
    if not bgm:
        print("  BGM: bgm/ 에 파일이 없어 BGM 없음 (YT_BGM=pad 로 임시 패드음)", flush=True)
        if video != out: os.replace(video, out)
        return out
    total = dur(video)
    ch = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0", video], capture_output=True, text=True).stdout.strip()
    # モノラル→ステレオの自動変換は -3dB されるので、pan で両chにそのままコピーする
    up = "pan=stereo|c0=c0|c1=c0" if ch == "1" else "aformat=channel_layouts=stereo"
    fc = (f"[0:a]aformat=sample_fmts=fltp:sample_rates=44100,{up},asplit=2[v1][v2];"
          f"[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume={db}dB,afade=t=in:d=2,afade=t=out:st={max(0,total-3):.2f}:d=3[b];"
          f"[b][v2]sidechaincompress=threshold=0.015:ratio=6:attack=30:release=900:makeup=1[bd];"
          f"[v1][bd]amix=inputs=2:duration=first:normalize=0[mix]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-stream_loop", "-1", "-i", bgm,
                    "-filter_complex", fc, "-map", "0:v", "-map", "[mix]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-t", f"{total:.2f}", "-movflags", "+faststart", out], check=True)
    return out

def concat(segs, out, bgm=True):
    lst = out + ".list.txt"; open(lst, "w").write("".join(f"file '{os.path.abspath(s)}'\n" for s in segs))
    tmp = out + ".nobgm.mp4" if bgm else out
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", tmp], check=True)
    if bgm:
        add_bgm(tmp, out)
        if os.path.exists(tmp): os.remove(tmp)
    return out

def split_parts(segs, limit_mb=27, boundary="_1.mp4"):
    """アップロード上限に合わせて、問題の切れ目 (boundary で終わるセグメントの前) で分割"""
    parts, cur, sz = [], [], 0
    for f in segs:
        z = os.path.getsize(f)
        if cur and f.endswith(boundary) and sz + z > limit_mb * 1048576: parts.append(cur); cur, sz = [], 0
        cur.append(f); sz += z
    parts.append(cur); return parts
