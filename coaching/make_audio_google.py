# -*- coding: utf-8 -*-
"""暗記ノート → 章ごとの日本語音声 (Google 版)。ElevenLabs 版と同じファイル名で static/audio/ に上書き。

エンジン:
  cloud : Google Cloud Text-to-Speech (API キー必要。数字・単位・分数・漢字の読みが正確、声は自然)
          キー:  echo 'AIza...' > .google_api_key   (Cloud Console → Text-to-Speech API 有効化 → 認証情報 → API キー)
          声:    echo 'ja-JP-Neural2-D' > .google_voice   (既定。男性。女性なら ja-JP-Neural2-B、
                 より自然な男性なら ja-JP-Chirp3-HD-Charon / Orus / Puck / Fenrir)
  gtts  : Google 翻訳の読み上げ (キー不要・女性の声・無料。pip install gTTS)

使い方 (VPS: cd ~/takken-note):
  python3 coaching/make_audio_google.py --subject toshi            # キーがあれば cloud、なければ gtts
  python3 coaching/make_audio_google.py --subject kenki --engine gtts
  python3 coaching/make_audio_google.py --subject toshi --dry-run  # 読み上げ文を表示 (課金なし)
漢字のままの台本 (Google は日本語の形態素解析を持つので読み間違いがほぼ無い) を送る。
"""
import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import subjects  # noqa: E402
import make_audio_eleven  # noqa: E402
from make_audio_eleven import chapter_text, cfg_file  # noqa: E402

make_audio_eleven.READINGS.clear()   # Google は漢字のままの方が正確に読む

API = "https://texttospeech.googleapis.com/v1/text:synthesize"
DEFAULT_VOICE = "ja-JP-Neural2-D"
MAX_BYTES = 4500   # Cloud TTS は 1 リクエスト 5000 バイトまで


def google_key():
    return os.environ.get("GOOGLE_TTS_API_KEY", "").strip() or cfg_file(".google_api_key")


def split_chunks(text):
    """段落 (改行) 単位で 4500 バイト以内に分割。"""
    chunks, cur = [], ""
    for para in text.split("\n"):
        cand = (cur + "\n" + para) if cur else para
        if len(cand.encode("utf-8")) > MAX_BYTES and cur:
            chunks.append(cur)
            cur = para
        else:
            cur = cand
    if cur:
        chunks.append(cur)
    return chunks


def shorten_sentences(text, limit=70):
    """Chirp3-HD は1文が長いと 400 になるので、長い文は読点を句点に替えて区切る。"""
    out = []
    for line in text.split("\n"):
        if len(line) <= limit:
            out.append(line)
            continue
        buf, segs = "", []
        for piece in line.split("、"):
            cand = (buf + "、" + piece) if buf else piece
            if len(cand) > limit and buf:
                segs.append(buf.rstrip("。") + "。")
                buf = piece
            else:
                buf = cand
        if buf:
            segs.append(buf)
        out.append("".join(segs))
    return "\n".join(out)


def tts_cloud(key, voice, rate, text, mp3):
    if "Chirp" in voice:
        text = shorten_sentences(text)
    parts = []
    for i, chunk in enumerate(split_chunks(text)):
        body = json.dumps({"input": {"text": chunk},
                           "voice": {"languageCode": "ja-JP", "name": voice},
                           "audioConfig": {"audioEncoding": "MP3", "speakingRate": rate,
                                           "sampleRateHertz": 24000}}).encode("utf-8")
        req = urllib.request.Request(f"{API}?key={key}", data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                audio = base64.b64decode(json.loads(r.read())["audioContent"])
        except urllib.error.HTTPError as e:
            sys.exit(f"Google TTS エラー {e.code}: {e.read().decode('utf-8', 'replace')[:600]}")
        part = f"{mp3[:-4]}_{i:02d}.mp3"
        with open(part, "wb") as f:
            f.write(audio)
        parts.append(part)
    concat(parts, mp3)


def tts_gtts(text, mp3):
    try:
        from gtts import gTTS
    except ImportError:
        sys.exit("gTTS がありません:  pip install gTTS")
    tmp = mp3[:-4] + "_raw.mp3"
    gTTS(text.replace("\n", "。"), lang="ja").save(tmp)
    concat([tmp], mp3)


def concat(parts, out):
    """mp3 の断片を連結し、一定の形式 (mono 24kHz 64kbps) に揃える。"""
    lst = out + ".txt"
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.basename(p)}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-ac", "1", "-ar", "24000", "-b:a", "64k", out], check=True, cwd=os.path.dirname(out))
    os.unlink(lst)
    for p in parts:
        os.unlink(p)


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return round(float(r.stdout.strip()))


def drop_other_cache(adir, name):
    """別エンジンのキャッシュ項目を消す (後でそのエンジンに戻したとき作り直されるように)。"""
    p = os.path.join(adir, ".eleven_cache.json")
    if os.path.exists(p):
        c = json.load(open(p))
        if name in c:
            del c[name]
            json.dump(c, open(p, "w"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", default="toshi", choices=list(subjects.SUBJECTS))
    ap.add_argument("--engine", default=cfg_file(".tts_engine") or "", help="cloud / gtts (未指定: キーがあれば cloud)")
    ap.add_argument("--voice", default=os.environ.get("GOOGLE_TTS_VOICE") or cfg_file(".google_voice") or DEFAULT_VOICE)
    ap.add_argument("--rate", type=float, default=1.0, help="話す速さ (0.25〜4.0)")
    ap.add_argument("--only", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "static", "audio"))
    a = ap.parse_args()

    KEY, CH, SUBJ = a.subject, subjects.chapters(a.subject), subjects.name(a.subject)
    texts = [chapter_text(c, "\n") for c in CH]
    if a.dry_run:
        for i, t in enumerate(texts, 1):
            print(f"===== 第{i}章 ({len(t)} 文字 / {len(t.encode('utf-8'))} bytes)\n{t}\n")
        print("合計", sum(map(len, texts)), "文字")
        return

    key = google_key()
    engine = a.engine if a.engine in ("cloud", "gtts") else ("cloud" if key else "gtts")
    if engine == "cloud" and not key:
        sys.exit("Google の API キーがありません:  echo 'AIza...' > .google_api_key  (または --engine gtts)")
    label = f"Google {a.voice}" if engine == "cloud" else "Google翻訳 (gTTS)"
    print(f"[{SUBJ}] エンジン: {label}  速さ: {a.rate}")

    os.makedirs(a.out, exist_ok=True)
    cache_p = os.path.join(a.out, ".google_cache.json")
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
    tracks, mp3s, made = [], [], 0
    for i, (c, text) in enumerate(zip(CH, texts), 1):
        name = f"{KEY}_{i:02d}.mp3"
        mp3 = os.path.join(a.out, name)
        h = hashlib.sha1(f"{engine}|{a.voice}|{a.rate}|{text}".encode("utf-8")).hexdigest()
        want = a.only is None or a.only == i
        if want and (a.force or cache.get(name) != h or not os.path.exists(mp3)):
            if os.environ.get("TTS_STUB"):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                                "-t", "1", "-b:a", "64k", mp3], check=True)
            elif engine == "cloud":
                tts_cloud(key, a.voice, a.rate, text, mp3)
            else:
                tts_gtts(text, mp3)
            cache[name] = h
            json.dump(cache, open(cache_p, "w"), indent=1)
            drop_other_cache(a.out, name)
            made += 1
            print(f"{i:02d} 生成 {len(text)}文字")
        elif not os.path.exists(mp3):
            sys.exit(f"{name} がありません (--only を外して全章を作ってください)")
        else:
            print(f"{i:02d} 変更なし (キャッシュ)")
        tracks.append({"n": i, "title": c["title"], "file": name, "sec": duration(mp3)})
        mp3s.append(mp3)

    allmp3 = os.path.join(a.out, f"{KEY}_all.mp3")
    tracks_p = os.path.join(a.out, f"{KEY}_tracks.json")
    if made == 0 and os.path.exists(allmp3) and os.path.exists(tracks_p):
        print("変更なし (全章キャッシュ済み)")
        return
    lst = os.path.join(a.out, f"concat_{KEY}.txt")
    with open(lst, "w") as f:
        for m in mp3s:
            f.write(f"file '{os.path.basename(m)}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", allmp3],
                   check=True, cwd=a.out)
    os.unlink(lst)
    meta = {"title": f"{SUBJ} 暗記ノート", "voice": label, "tracks": tracks,
            "all": {"file": f"{KEY}_all.mp3", "sec": duration(allmp3)}}
    json.dump(meta, open(tracks_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"完了: {made} 章生成 / 通し {meta['all']['sec']} 秒")


if __name__ == "__main__":
    main()
