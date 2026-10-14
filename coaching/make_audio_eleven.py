# -*- coding: utf-8 -*-
"""都市計画法 暗記ノート → 章ごとの日本語音声 (ElevenLabs 版)

Open JTalk 版 (make_audio.py) と同じファイル名で static/audio/ に上書きするので、
サイトの学習タブ(プレイヤー)側は変更不要。

準備:
  1) https://elevenlabs.io でアカウント作成 → Profile → API Keys でキー発行
  2) キーを環境変数か、リポジトリ直下の .eleven_api_key (git 管理外) に保存
       echo 'sk_xxxx' > .eleven_api_key
  3) ffmpeg が必要 (通し版の連結・長さ計測):  sudo apt-get install -y ffmpeg

使い方 (VPS なら  cd ~/takken-note  で):
  python3 coaching/make_audio_eleven.py --list            # 使える声の一覧 (日本語の声を探す)
  python3 coaching/make_audio_eleven.py --dry-run         # 読み上げ文と文字数だけ表示 (課金なし)
  python3 coaching/make_audio_eleven.py --voice <名前かID> # 生成 (変更のない章はキャッシュで再課金なし)
  python3 coaching/make_audio_eleven.py --only 3 --force  # 第3章だけ作り直す
  その後:  git add static/audio && git commit -m "ElevenLabs 音声" && git push origin HEAD

文字数: 全13章で約 7,300 文字 → Free プラン(月1万文字)でも1回は作れる。Starter($5/月, 3万文字)なら余裕。
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import toshi_gen  # noqa: E402
from make_audio import speakable  # noqa: E402

API = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_64"
PAUSE_BREAK = '<break time="0.7s" />'   # --breaks 指定時 (文字数に加算される可能性あり)
PAUSE_NL = "\n\n"                       # 既定: 改行で自然な間 (課金なし)

# ElevenLabs が漢字を読み間違えたら、ここに「用語 → 読み(ひらがな)」を足して --force で作り直す。
READINGS = {
    # "線引き": "せんびき",
}


def api_key():
    k = os.environ.get("ELEVEN_API_KEY", "").strip()
    if not k:
        p = os.path.join(ROOT, ".eleven_api_key")
        if os.path.exists(p):
            k = open(p, encoding="utf-8").read().strip()
    if not k:
        sys.exit("API キーがありません:  export ELEVEN_API_KEY=sk_xxx  または  echo 'sk_xxx' > .eleven_api_key")
    return k


def call(path, data=None, key=None, raw=False):
    req = urllib.request.Request(API + path, headers={"xi-api-key": key, "Accept": "application/json"})
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs エラー {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
    return body if raw else json.loads(body)


def voices(key):
    return call("/voices", key=key)["voices"]


def pick_voice(key, want):
    vs = voices(key)
    if want:
        for v in vs:
            if want in (v["voice_id"], v["name"]):
                return v
        sys.exit(f"声 '{want}' が見つかりません。--list で確認してください。")
    for v in vs:  # 日本語ラベルの声があればそれ、なければ Sarah (multilingual で日本語も読める)
        if (v.get("labels") or {}).get("language", "").lower().startswith("ja"):
            return v
    for v in vs:
        if v["name"] == "Sarah":
            return v
    return vs[0]


def chapter_text(c, pause=PAUSE_NL):
    def fix(s):
        s = speakable(s)
        for k, v in READINGS.items():
            s = s.replace(k, v)
        for k, v in zip("①②③④⑤⑥⑦⑧⑨⑩", "1234567890"):
            s = s.replace(k, f"その{v}、")
        s = s.replace("！。", "！").replace("？。", "？")
        s = re.sub(r"、{2,}", "、", s)
        return s.rstrip("。")

    title = c["title"].replace("　", "、").replace("――", "、").replace("―", "、")
    lines = [f"{title}。", fix(c["meaning"]) + "。"]
    for n, it in enumerate(c["items"], 1):
        lines.append(f"{n}。{fix(it)}。")
    lines.append("一文。" + fix(c["one"]) + "。")
    return pause.join(lines)


def tts(key, voice_id, model, text, mp3):
    body = call(f"/text-to-speech/{voice_id}?output_format={OUTPUT_FORMAT}",
                data={"text": text, "model_id": model,
                      "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.0,
                                         "use_speaker_boost": True}},
                key=key, raw=True)
    with open(mp3, "wb") as f:
        f.write(body)


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return round(float(r.stdout.strip()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="声の一覧を表示して終了")
    ap.add_argument("--voice", default=os.environ.get("ELEVEN_VOICE", ""), help="声の名前か voice_id")
    ap.add_argument("--model", default=os.environ.get("ELEVEN_MODEL", DEFAULT_MODEL))
    ap.add_argument("--only", type=int, help="この章番号だけ生成")
    ap.add_argument("--force", action="store_true", help="キャッシュを無視して作り直す")
    ap.add_argument("--dry-run", action="store_true", help="文章と文字数だけ表示 (API を呼ばない)")
    ap.add_argument("--breaks", action="store_true", help="改行の代わりに <break> タグで0.7秒の間を入れる")
    ap.add_argument("--out", default=os.path.join(ROOT, "static", "audio"))
    a = ap.parse_args()

    texts = [chapter_text(c, PAUSE_BREAK.join(("\n", "\n")) if a.breaks else PAUSE_NL) for c in toshi_gen.CHAPTERS]
    if a.dry_run:
        for i, t in enumerate(texts, 1):
            print(f"===== 第{i}章 ({len(t)} 文字)\n{t}\n")
        print("合計", sum(map(len, texts)), "文字")
        return

    key = api_key()
    if a.list:
        for v in voices(key):
            lab = v.get("labels") or {}
            print(f"{v['voice_id']}  {v['name']:<14} {lab.get('language','?'):<6} {lab.get('gender','')} {lab.get('accent','')} {lab.get('description','')}")
        return
    if not subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0:
        sys.exit("ffmpeg がありません:  sudo apt-get install -y ffmpeg")

    v = pick_voice(key, a.voice)
    print(f"声: {v['name']} ({v['voice_id']})  モデル: {a.model}")
    os.makedirs(a.out, exist_ok=True)
    cache_p = os.path.join(a.out, ".eleven_cache.json")
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}

    tracks, mp3s, used = [], [], 0
    for i, (c, text) in enumerate(zip(toshi_gen.CHAPTERS, texts), 1):
        name = f"toshi_{i:02d}.mp3"
        mp3 = os.path.join(a.out, name)
        h = hashlib.sha1(f"{v['voice_id']}|{a.model}|{text}".encode("utf-8")).hexdigest()
        want = a.only is None or a.only == i
        if want and (a.force or cache.get(name) != h or not os.path.exists(mp3)):
            if os.environ.get("ELEVEN_STUB"):  # テスト用: API を呼ばず無音を書く
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                                "-t", "2", "-b:a", "64k", mp3], check=True)
            else:
                tts(key, v["voice_id"], a.model, text, mp3)
            cache[name] = h
            used += len(text)
            json.dump(cache, open(cache_p, "w"), indent=1)
            print(f"{i:02d} 生成 {len(text)}文字")
        elif not os.path.exists(mp3):
            sys.exit(f"{name} がありません (--only を外して全章を作ってください)")
        else:
            print(f"{i:02d} 変更なし (キャッシュ)")
        tracks.append({"n": i, "title": c["title"], "file": name, "sec": duration(mp3)})
        mp3s.append(mp3)

    lst = os.path.join(a.out, "concat.txt")
    with open(lst, "w") as f:
        for m in mp3s:
            f.write(f"file '{os.path.basename(m)}'\n")
    allmp3 = os.path.join(a.out, "toshi_all.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", allmp3], check=True, cwd=a.out)
    os.unlink(lst)
    meta = {"title": "都市計画法 暗記ノート", "voice": v["name"], "tracks": tracks,
            "all": {"file": "toshi_all.mp3", "sec": duration(allmp3)}}
    with open(os.path.join(a.out, "toshi_tracks.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"完了: 使用 {used} 文字 / 通し {meta['all']['sec']} 秒 → {a.out}")


if __name__ == "__main__":
    main()
