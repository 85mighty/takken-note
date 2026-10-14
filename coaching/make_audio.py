# -*- coding: utf-8 -*-
"""都市計画法 暗記ノート → 章ごとの日本語音声 (Open JTalk → mp3)

python3 coaching/make_audio.py            # static/audio/toshi_01.mp3 … toshi_13.mp3, toshi_all.mp3, toshi_tracks.json
필요: apt-get install open-jtalk open-jtalk-mecab-naist-jdic hts-voice-nitech-jp-atr503-m001 ffmpeg
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import toshi_gen  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "static", "audio")
DIC = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE = "/usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice"


def speakable(s):
    """暗記ノートの表記を、読み上げ用の自然な日本語に変換する。"""
    s = re.sub(r"\{\{(.+?)\}\}", r"\1", s)
    s = re.sub(r"(\d),(\d{3})", r"\1\2", s)            # 1,000 → 1000
    s = re.sub(r"(\d+)/(\d+)", r"\2分の\1", s)           # 2/3 → 3分の2
    s = re.sub(r"(\d)\s*㎡", r"\1平方メートル", s)
    s = re.sub(r"(\d)\s*ha", r"\1ヘクタール", s)
    s = re.sub(r"(\d)\s*m\b", r"\1メートル", s)
    s = re.sub(r"(\d)\s*t\b", r"\1トン", s)
    s = s.replace("％", "パーセント").replace("%", "パーセント")
    s = s.replace(" or ", "、または、").replace("OK", "オーケー")
    s = s.replace("○", "マル").replace("×", "バツ").replace("〜", "から")
    s = s.replace("＝", "は、").replace("→", "、").replace("／", "、").replace("・", "、")
    s = s.replace("（", "、").replace("）", "、").replace("「", "").replace("」", "")
    s = s.replace("＋", "、プラス、").replace("&", "と").replace("＆", "と")
    s = s.replace("〜", "から").replace("…", "。")
    s = re.sub(r"、{2,}", "、", s)
    s = s.replace("：", "、").replace("。。", "。")
    s = re.sub(r"、([。、])", r"\1", s)
    return s.strip("、 ")


def chapter_script(i, c):
    lines = [f"{c['title'].replace('　', '、')}。", speakable(c["meaning"]).rstrip("。") + "。"]
    for n, it in enumerate(c["items"], 1):
        body = speakable(it).rstrip("。")
        lines.append(f"{n}。{body}。")
    lines.append("一文。" + speakable(c["one"]) + "。")
    return "\n".join(lines)


def tts(text, wav):
    """open_jtalk은 1行しか読まないので、行ごとに合成して無音0.6秒を挟んで連結する。"""
    parts = []
    base = wav[:-4]
    for i, line in enumerate(l for l in text.split("\n") if l.strip()):
        txt, part = f"{base}_{i:03d}.txt", f"{base}_{i:03d}.wav"
        with open(txt, "w", encoding="utf-8") as f:
            f.write(line)
        subprocess.run(["open_jtalk", "-x", DIC, "-m", VOICE, "-r", "1.0", "-a", "0.55",
                        "-ow", part, txt], check=True)
        os.unlink(txt)
        padded = part[:-4] + "p.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", part, "-af", "apad=pad_dur=0.6", padded], check=True)
        os.unlink(part)
        parts.append(padded)
    lst = base + "_list.txt"
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.basename(p)}'\n")
    # 각 조각 뒤에 0.6초 무음 (apad) → 연결
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", wav], check=True, cwd=os.path.dirname(wav))
    for p in parts:
        os.unlink(p)
    os.unlink(lst)


def to_mp3(wav, mp3):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ac", "1", "-ar", "24000",
                    "-b:a", "48k", mp3], check=True)
    os.unlink(wav)


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return round(float(r.stdout.strip()))


def main():
    os.makedirs(OUT, exist_ok=True)
    tracks, mp3s = [], []
    for i, c in enumerate(toshi_gen.CHAPTERS, 1):
        wav = os.path.join(OUT, f"toshi_{i:02d}.wav")
        mp3 = os.path.join(OUT, f"toshi_{i:02d}.mp3")
        tts(chapter_script(i, c), wav)
        to_mp3(wav, mp3)
        d = duration(mp3)
        tracks.append({"n": i, "title": c["title"], "file": f"toshi_{i:02d}.mp3", "sec": d})
        mp3s.append(mp3)
        print(f"{i:02d} {d}s {c['title']}")
    lst = os.path.join(OUT, "concat.txt")
    with open(lst, "w") as f:
        for m in mp3s:
            f.write(f"file '{os.path.basename(m)}'\n")
    allmp3 = os.path.join(OUT, "toshi_all.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy", allmp3], check=True, cwd=OUT)
    os.unlink(lst)
    meta = {"title": "都市計画法 暗記ノート", "tracks": tracks,
            "all": {"file": "toshi_all.mp3", "sec": duration(allmp3)}}
    with open(os.path.join(OUT, "toshi_tracks.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("all", meta["all"]["sec"], "s")


if __name__ == "__main__":
    main()
