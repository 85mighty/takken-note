# -*- coding: utf-8 -*-
"""YouTube に貼るタイトル・概要欄・タグを spec から組み立てる。
  {{chapters}} … 書き出した動画の目次 (manifest。なければ下書きの目安時間)
  {{blog}}     … ブログ記事への誘導 (spec.blog.url。未発行なら予定URL)
  {{related}}  … 関連動画 (spec.related の key を videos.json の URL に)
  python3 ytext.py specs/R8_xxx.json
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
OUT = os.environ.get("YT_OUT", os.path.join(HERE, "out"))
BLOG_SITE = "https://takken.ekunblog.com"

DEFAULT_DESC = """{{lead}}

▼目次
{{chapters}}

{{blog}}

▼関連動画
{{related}}

#宅建 #宅建士 #宅建試験 #宅建2026"""

def _mmss(t):
    t = int(t); return f"{t//3600}:{t%3600//60:02d}:{t%60:02d}" if t >= 3600 else f"{t//60:02d}:{t%60:02d}"

def chapters(spec):
    """(本文, 種類) 種類 = final | draft | none"""
    d = os.path.join(OUT, spec["outdir"])
    for fn, kind in ((f"{spec['name']}.manifest.json", "final"), (f"{spec['name']}.draft.json", "draft")):
        p = os.path.join(d, fn)
        if os.path.exists(p):
            man = json.load(open(p, encoding="utf-8"))
            rows, last = [], None
            for m in man["slides"]:
                if m["title"] == last: continue          # 同じ見出しが続くスライドはまとめる
                rows.append(f"{_mmss(m['start'])} {m['title']}"); last = m["title"]
            return "\n".join(rows), kind
    return "00:00 はじめに", "none"

def blog_url(spec):
    b = spec.get("blog") or {}
    if b.get("url"): return b["url"], True
    if b.get("slug"): return f"{BLOG_SITE}/{b['slug']}/", False
    return "", False

def related(spec, reg=None):
    import registry
    reg = reg or registry.load()
    rows, missing = [], []
    for k in spec.get("related") or []:
        v = registry.get(reg, k)
        if not v: missing.append(k); continue
        label = v.get("label") or v.get("yt_title") or k
        if v.get("url"): rows.append(f"・{label} → {v['url']}")
        else: missing.append(label); rows.append(f"・{label} → （URL未登録）")
    return "\n".join(rows), missing

def compose(spec):
    yt = spec.get("youtube") or {}
    desc = yt.get("description") or DEFAULT_DESC
    lead = (spec.get("blog") or {}).get("excerpt") or spec.get("label", "")
    ch, kind = chapters(spec)
    burl, published = blog_url(spec)
    btitle = (spec.get("blog") or {}).get("title") or spec.get("label", "")
    blog = f"▼ブログで詳しく（表・リンクつき）\n{btitle}\n{burl}" if burl else ""
    rel, missing = related(spec)
    if not rel: desc = desc.replace("▼関連動画\n{{related}}", "")
    desc = desc.replace("{{lead}}", lead).replace("{{chapters}}", ch).replace("{{blog}}", blog).replace("{{related}}", rel or "")
    if "{{blog}}" not in (yt.get("description") or DEFAULT_DESC) and burl and burl not in desc:
        desc = desc.replace("\n▼目次", f"\n{blog}\n\n▼目次", 1) if "\n▼目次" in desc else desc + "\n\n" + blog
    while "\n\n\n" in desc: desc = desc.replace("\n\n\n", "\n\n")
    warn = []
    if kind == "draft": warn.append("目次は下書きの目安時間です。音声つきで書き出すと正確な時間になります")
    if kind == "none": warn.append("目次はまだありません（書き出し後に入ります）")
    if burl and not published: warn.append("ブログはまだ発行していません（予定のURLを入れています）")
    if missing: warn.append("関連動画の URL がないもの: " + "、".join(missing))
    if len(desc) > 5000: warn.append(f"概要欄が {len(desc)} 字あります（上限5000字）")
    tags = yt.get("tags") or []
    return {"title": yt.get("title") or spec.get("label", ""), "description": desc.strip(), "tags": ", ".join(tags),
            "warn": warn, "chapters_kind": kind, "blog_url": burl, "blog_published": published,
            "title_len": len(yt.get("title") or "")}

if __name__ == "__main__":
    sp = json.load(open(sys.argv[1], encoding="utf-8")); r = compose(sp)
    print("【タイトル】\n" + r["title"] + "\n\n【概要欄】\n" + r["description"] + "\n\n【タグ】\n" + r["tags"])
    for w in r["warn"]: print("※", w)
