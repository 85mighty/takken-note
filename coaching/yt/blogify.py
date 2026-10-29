# -*- coding: utf-8 -*-
"""spec から WordPress (takken.ekunblog.com) の記事を作って発行する。
  python3 blogify.py specs/R8_xxx.json            … coaching/blog/<slug>.html を作るだけ
  python3 blogify.py specs/R8_xxx.json --publish  … 画像を上げて発行し、記事URLを spec に保存
記事の形: 導入 → YouTube 埋め込み → スライドごとに 見出し・イラスト・要点・解説 → 動画への誘導・関連動画
"""
import argparse, html, json, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "coaching", "blog"))
BLOG_DIR = os.path.join(ROOT, "coaching", "blog")
CHANNEL = "https://www.youtube.com/@nippon-real"

INLINE = {
    "key": "background:#fff3c4;border-left:6px solid #e0a800;padding:12px 16px;font-weight:bold;margin:1em 0;",
    "note": "color:#666;font-size:0.9em;",
    "big": "font-size:2.2em;font-weight:bold;color:#c0392b;text-align:center;margin:0.5em 0;",
}
TD = {"hi": "background:#ffe8e4;font-weight:bold;", "lo": "background:#e8f0ff;", "c": "text-align:center;"}

def _p(text):
    return f"<!-- wp:paragraph -->\n<p>{text}</p>\n<!-- /wp:paragraph -->"

def _speech_paras(speech):
    """読み上げ文を 2〜3文ずつの段落に"""
    sents = [s for s in re.split(r"(?<=。)", speech or "") if s.strip()]
    out, cur = [], ""
    for s in sents:
        cur += s
        if len(cur) > 110: out.append(cur); cur = ""
    if cur: out.append(cur)
    return [_p(html.escape(x.strip())) for x in out]

def _convert(body):
    """スライドの HTML をブログ用に (クラス → インライン、表 → 表ブロック)"""
    b = body or ""
    b = re.sub(r"<div class='two'>\s*<div>", "<div>", b)
    b = re.sub(r"</div>\s*<div>", "</div>\n<div>", b)
    for cls, st in INLINE.items():
        b = re.sub(rf"<(div|p) class='{cls}'>", rf"<\1 style='{st}'>", b)
    b = re.sub(r"<small>", "<br><small>", b)
    for cls, st in TD.items():
        b = re.sub(rf"<(td|th) class='{cls}'>", rf"<\1 style='{st}'>", b)
    b = re.sub(r"<tr class='now'>", "<tr style='background:#fff3c4;font-weight:bold;'>", b)
    b = re.sub(r"<ul class='steps'>", "<ul>", b)
    b = re.sub(r"<table>([\s\S]*?)</table>", r"<figure class='wp-block-table'><table>\1</table></figure>", b)
    return f"<!-- wp:html -->\n{b.strip()}\n<!-- /wp:html -->" if b.strip() else ""

def _raster(path):
    """SVG のイラストは PNG にしてから上げる (WordPress は SVG を受け付けないことが多い)"""
    if not path.endswith(".svg"): return path
    png = path[:-4] + ".png"
    if os.path.exists(png): return png
    from weasyprint import HTML
    with tempfile.TemporaryDirectory() as td:
        pdf = os.path.join(td, "a.pdf")
        HTML(string=f"<html><head><style>@page{{size:800px 600px;margin:0}}body{{margin:0}}</style></head>"
                    f"<body><img src='file://{path}' style='width:800px;height:600px'></body></html>").write_pdf(pdf)
        subprocess.run(["pdftoppm", "-singlefile", "-png", "-r", "96", pdf, png[:-4]], check=True)
    return png

def build(spec, image_url=None):
    """記事の HTML (WordPress ブロック)。image_url(path) を渡すとイラストを入れる"""
    import illust, registry
    reg = registry.load()
    blog = spec.get("blog") or {}
    slides = spec["slides"]
    parts = []
    lead = blog.get("excerpt") or ""
    if lead: parts.append(_p(html.escape(lead)))
    if slides and not slides[0].get("title"):                 # 表紙の読み上げを導入に
        parts += _speech_paras(slides[0].get("speech", "")); slides = slides[1:]
    parts.append(_p("動画でも解説しています。"))
    parts.append("<!--YOUTUBE_EMBED-->")
    for s in slides:
        if s.get("title"):
            parts.append(f"<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">{html.escape(s['title'].replace('｜', '：'))}</h2>\n<!-- /wp:heading -->")
        p = illust.path_for(s)
        if p and image_url:
            try:
                u = image_url(_raster(p))
                parts.append(f"<!-- wp:image {{\"align\":\"center\",\"width\":\"420px\"}} -->\n<figure class=\"wp-block-image aligncenter is-resized\"><img src=\"{u}\" alt=\"\" style=\"width:420px\"/></figure>\n<!-- /wp:image -->")
            except Exception as e:
                print("  イラストを上げられませんでした:", e, flush=True)
        c = _convert(s.get("body", ""))
        if c: parts.append(c)
        parts += _speech_paras(s.get("speech", ""))
    parts.append("<!--YOUTUBE_LINK-->")
    rel = []
    for k in spec.get("related") or []:
        v = registry.get(reg, k)
        if v and v.get("url"):
            rel.append(f"<li><a href=\"{v['url']}\" target=\"_blank\" rel=\"noopener\">{html.escape(v.get('label') or v.get('yt_title') or k)}</a></li>")
    if rel:
        parts.append("<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">関連動画</h2>\n<!-- /wp:heading -->")
        parts.append("<!-- wp:list -->\n<ul class=\"wp-block-list\">\n" + "\n".join(rel) + "\n</ul>\n<!-- /wp:list -->")
    parts.append(_p(f"宅建の最新情報は YouTube チャンネル <a href=\"{CHANNEL}\" target=\"_blank\" rel=\"noopener\">NIPPONリアル</a> でも発信しています。"))
    return "\n\n".join(parts) + "\n"

def youtube_url(spec):
    import registry
    v = registry.get(registry.load(), spec["name"])
    return (spec.get("youtube") or {}).get("url") or (v or {}).get("url") or ""

def save_html(spec, content):
    slug = (spec.get("blog") or {}).get("slug") or spec["name"].lower().replace("_", "-")
    p = os.path.join(BLOG_DIR, f"{slug}.html")
    open(p, "w", encoding="utf-8").write(content)
    return p

def publish(spec_path, draft=False, log=print):
    import publish_wp, registry
    spec = json.load(open(spec_path, encoding="utf-8"))
    blog = spec.setdefault("blog", {})
    if not blog.get("slug"): blog["slug"] = spec["name"].lower().replace("_", "-")
    if not blog.get("title"): blog["title"] = (spec.get("youtube") or {}).get("title") or spec.get("label", "")
    au = publish_wp.auth()
    content = build(spec, image_url=lambda p: publish_wp.upload_media(p, au=au))
    save_html(spec, content)
    yt = youtube_url(spec)
    if not yt: log("※ YouTube の URL がまだないので、動画の埋め込みなしで発行します（URLが入ったらもう一度押すと埋め込まれます）")
    link, action, status, slug = publish_wp.publish(content, blog["title"], blog["slug"], blog.get("excerpt", ""), yt, draft, au=au)
    log(f"ブログを{action}しました（{status}）: {link}")
    sp = json.load(open(spec_path, encoding="utf-8"))          # 発行中に編集されていてもよいように読み直す
    sp.setdefault("blog", {}).update({"slug": slug or blog["slug"], "title": blog["title"], "url": link})
    order = ["topic", "script", "draft", "voiced", "uploaded", "blogged"]
    if status == "publish" and order.index(sp.get("status", "script")) < order.index("blogged"): sp["status"] = "blogged"
    with open(spec_path + ".tmp", "w", encoding="utf-8") as f: json.dump(sp, f, ensure_ascii=False, indent=1)
    os.replace(spec_path + ".tmp", spec_path)
    reg = registry.load(); registry.upsert(reg, sp["name"], blog_url=link); registry.save(reg)
    return link

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("--publish", action="store_true"); ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()
    if a.publish:
        import publish_wp
        try: publish(a.spec, a.draft, log=lambda m: print(m, flush=True))
        except publish_wp.WPError as e: sys.exit(str(e))
    else:
        sp = json.load(open(a.spec, encoding="utf-8")); print("保存:", save_html(sp, build(sp)))
