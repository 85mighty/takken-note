# -*- coding: utf-8 -*-
"""動画 URL 台帳 (videos.json)。YouTube 概要欄の「関連動画」リンクや、ブログ埋め込みに使う。
  python3 registry.py --fetch   … チャンネルの動画一覧を yt-dlp で取り、台帳の URL を自動で埋める (VPS で実行)
  台帳の各動画: key（spec 名など）, label（表示名）, title（YouTube のタイトル）, match（タイトル照合用の語）, url
"""
import argparse, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PATH = os.path.join(HERE, "videos.json")
SPECS = os.path.join(HERE, "specs")

def load():
    if os.path.exists(PATH):
        return json.load(open(PATH, encoding="utf-8"))
    return {"channel": "https://www.youtube.com/@nippon-real", "videos": []}

def save(reg):
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(reg, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PATH)

def get(reg, key):
    return next((v for v in reg["videos"] if v.get("key") == key), None)

def upsert(reg, key, **kw):
    v = get(reg, key)
    if not v:
        v = {"key": key}; reg["videos"].append(v)
    v.update({k: x for k, x in kw.items() if x is not None})
    return v

def _norm(s):
    return re.sub(r"[\s　｜|【】\[\]（）()「」『』・、。！!？?]", "", s or "")

def _ytdlp():
    p = os.path.join(ROOT, ".venv", "bin", "yt-dlp")
    return p if os.path.exists(p) else "yt-dlp"

def channel_videos(channel):
    out = []
    for tab in ("videos", "shorts"):
        r = subprocess.run([_ytdlp(), "--no-warnings", "--flat-playlist", "-J", f"{channel.rstrip('/')}/{tab}"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout:
            for e in json.loads(r.stdout).get("entries", []):
                if e.get("id"):
                    out.append({"id": e["id"], "title": e.get("title") or "", "short": tab == "shorts",
                                "url": f"https://youtu.be/{e['id']}" if tab == "videos" else f"https://youtube.com/shorts/{e['id']}"})
        else:
            print(f"  ! {tab}: {(r.stderr or '').strip().splitlines()[-1:] }", file=sys.stderr)
    return out

def match_entry(v, chans):
    """台帳の1本に合う動画を探す: タイトル完全一致 → match の語がすべて入っている動画"""
    if v.get("title"):
        t = _norm(v["title"])
        for c in chans:
            if _norm(c["title"]) == t: return c
    words = v.get("match") or []
    if words:
        hits = [c for c in chans if all(_norm(w) in _norm(c["title"]) for w in words)]
        if len(hits) >= 1: return sorted(hits, key=lambda c: c["short"])[0]
    return None

def fetch():
    reg = load()
    # spec の YouTube タイトルも照合に使う
    if os.path.isdir(SPECS):
        for f in os.listdir(SPECS):
            if f.endswith(".json"):
                sp = json.load(open(os.path.join(SPECS, f), encoding="utf-8"))
                yt = sp.get("youtube") or {}
                if yt.get("title"):
                    upsert(reg, sp["name"], label=sp.get("label"), title=yt["title"])
    chans = channel_videos(reg["channel"])
    print(f"채널 영상: {len(chans)}편")
    if not chans: sys.exit("영상 목록을 가져오지 못했습니다 (yt-dlp 업데이트: .venv/bin/pip install -U yt-dlp)")
    used, filled = set(), 0
    for v in reg["videos"]:
        if v.get("url"):
            used.add(v["url"]); continue
        c = match_entry(v, chans)
        if c and c["url"] not in used:
            v["url"] = c["url"]; v["yt_title"] = c["title"]; used.add(c["url"]); filled += 1
            print(f"  ✓ {v.get('label') or v['key']} → {c['url']}")
    # 台帳にない動画も記録しておく（関連動画の候補になる）
    known = {v.get("url") for v in reg["videos"]}
    for c in chans:
        if c["url"] not in known:
            reg["videos"].append({"key": c["id"], "label": c["title"][:40], "yt_title": c["title"], "url": c["url"], "short": c["short"], "auto": True})
    reg["fetched_at"] = time.strftime("%Y-%m-%d %H:%M")
    save(reg)
    print(f"URL 을 채운 영상: {filled}편 / 대장 {len(reg['videos'])}편")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--fetch", action="store_true"); a = ap.parse_args()
    if a.fetch: fetch()
    else: print(json.dumps(load(), ensure_ascii=False, indent=1)[:3000])
