#!/usr/bin/env python3
"""宅建チャンネルのベンチマーク収集 (VPS で実行。YouTube に直接つながる環境が必要)
  seido-tube/scripts/01_collect_channel.py と同じ方式:
   1) yt-dlp --flat-playlist でチャンネルの動画一覧を1回で取る（ボット判定にかかりにくい）→ id・タイトル・再生数・長さ・おおよその投稿日
   2) YouTube Data API キーがあれば（.youtube_api_key または環境変数 YOUTUBE_API_KEY）正確な投稿日・高評価・コメント数
  使い方:  python3 coaching/bench/collect.py            … channels.json の全チャンネル
           python3 coaching/bench/collect.py --only 棚田
  出力:    coaching/bench/out/videos_<slug>.json, out/channels_resolved.json
"""
import argparse, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / "out"; OUT.mkdir(exist_ok=True)

def ytdlp():
    venv = ROOT / ".venv" / "bin" / "yt-dlp"
    return str(venv) if venv.exists() else "yt-dlp"

def run(args):
    r = subprocess.run([ytdlp(), "--no-warnings"] + args, capture_output=True, text=True)
    if r.returncode != 0 and r.stderr.strip():
        print("   !", r.stderr.strip().splitlines()[-1][:200], file=sys.stderr)
    return r.stdout if r.returncode == 0 else ""

def slug(name):
    s = re.sub(r"[^\w]+", "_", name).strip("_")
    return s[:40] or "channel"

def resolve(name):
    """チャンネル名で動画検索し、いちばん多く出てきたチャンネルの URL を返す"""
    out = run(["--flat-playlist", "-J", f"ytsearch20:{name}"])
    if not out: return None, None
    from collections import Counter
    ents = json.loads(out).get("entries", [])
    cnt = Counter((e.get("channel_url") or e.get("uploader_url"), e.get("channel") or e.get("uploader")) for e in ents if e.get("channel_url") or e.get("uploader_url"))
    if not cnt: return None, None
    # 名前が一致するチャンネルを優先
    key = re.sub(r"\s", "", name)
    for (url, ch), _ in cnt.most_common():
        if ch and (re.sub(r"\s", "", ch) in key or key in re.sub(r"\s", "", ch)): return url, ch
    (url, ch), _ = cnt.most_common(1)[0]
    return url, ch

def flat_list(channel_url):
    def _flat(extra):
        out = run(["--flat-playlist", "-J"] + extra + [f"{channel_url.rstrip('/')}/videos"])
        return json.loads(out).get("entries", []) if out else []
    ents = _flat(["--extractor-args", "youtube:lang=ja", "--extractor-args", "youtubetab:approximate_date"])
    if ents and all(e.get("view_count") is None for e in ents):
        ents2 = _flat(["--extractor-args", "youtubetab:approximate_date"])
        if any(e.get("view_count") is not None for e in ents2):
            titles = {e["id"]: e.get("title") for e in ents if e.get("id")}
            for e in ents2: e["title"] = titles.get(e.get("id")) or e.get("title")
            ents = ents2
    rows = []
    for e in ents:
        if e.get("id"):
            rows.append(dict(id=e["id"], title=e.get("title") or "", view_count=e.get("view_count"), duration=e.get("duration"),
                             upload_date=e.get("upload_date"), like_count=None, comment_count=None))
    return rows

def iso_dur(s):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    return (int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0)) if m else None

def api_key():
    k = os.environ.get("YOUTUBE_API_KEY")
    if k: return k.strip()
    p = ROOT / ".youtube_api_key"
    return p.read_text().strip() if p.exists() else None

def api_meta(rows, key):
    by = {r["id"]: r for r in rows}; ids = list(by)
    for i in range(0, len(ids), 50):
        q = urllib.parse.urlencode({"part": "snippet,statistics,contentDetails", "id": ",".join(ids[i:i+50]), "key": key, "hl": "ja"})
        with urllib.request.urlopen(f"https://www.googleapis.com/youtube/v3/videos?{q}", timeout=60) as r:
            for it in json.load(r).get("items", []):
                v = by[it["id"]]; sn, st, cd = it["snippet"], it.get("statistics", {}), it.get("contentDetails", {})
                v.update(title=sn.get("title") or v["title"], upload_date=sn["publishedAt"][:10].replace("-", ""),
                         view_count=int(st.get("viewCount", v["view_count"] or 0)),
                         like_count=int(st["likeCount"]) if "likeCount" in st else None,
                         comment_count=int(st["commentCount"]) if "commentCount" in st else None,
                         duration=iso_dur(cd.get("duration")) or v["duration"])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=""); a = ap.parse_args()
    conf = json.load(open(HERE / "channels.json", encoding="utf-8"))["channels"]
    resolved_p = OUT / "channels_resolved.json"
    resolved = json.load(open(resolved_p, encoding="utf-8")) if resolved_p.exists() else {}
    key = api_key()
    print(f"yt-dlp: {ytdlp()}  /  Data API: {'あり' if key else 'なし（投稿日はおおよそ）'}")
    for c in conf:
        if a.only and a.only not in c["name"]: continue
        name = c["name"]; url = c.get("url") or resolved.get(name, {}).get("url")
        found = None
        if not url:
            url, found = resolve(name)
            if not url: print(f"✗ {name}: チャンネルが見つかりません（channels.json に url を入れてください）"); continue
        print(f"■ {name}  →  {url}" + (f"（検索で見つかったチャンネル名: {found}）" if found else ""))
        rows = flat_list(url)
        if not rows: print("   動画一覧が取れませんでした"); continue
        if key:
            try: api_meta(rows, key)
            except Exception as e: print("   Data API 失敗:", e)
        rows.sort(key=lambda r: r["view_count"] or 0, reverse=True)
        s = slug(name)
        json.dump({"name": name, "url": url, "self": bool(c.get("self")), "collected_at": time.strftime("%Y-%m-%d %H:%M"), "videos": rows},
                  open(OUT / f"videos_{s}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        resolved[name] = {"url": url, "found_name": found, "slug": s, "n": len(rows)}
        print(f"   {len(rows)}本  再生数あり {sum(1 for r in rows if r['view_count'] is not None)}  投稿日あり {sum(1 for r in rows if r['upload_date'])}")
        time.sleep(2)
    json.dump(resolved, open(resolved_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
