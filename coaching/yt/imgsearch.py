# -*- coding: utf-8 -*-
"""実在の画像（会社ロゴ・写真）をウェブから取ってきてスライドに使う。
  候補の出どころ（上から順に、鍵がある物だけ使う）
    brave    … Brave Image Search  (.brave_api_key / BRAVE_API_KEY)
    serpapi  … Google 画像検索 via SerpAPI (.serpapi_api_key / SERPAPI_KEY)
    wiki     … Wikidata のロゴ(P154) と Wikipedia(ja) の代表画像。鍵いらず。ロゴはほぼこれで足りる
  本文の書き方:  {{img:住友不動産 ロゴ}}   {{img:三井不動産 ロゴ|h=48}}   → <img> に置き換わる（高さ px、既定 44）
  取った画像は illust/web_<md5>.png に保存（同じ URL は二度取らない）。
  スタジオで選び直した画像は illust/web_pick.json に 検索語→ファイル で覚える。
"""
import hashlib, io, json, os, re, sys, tempfile, time, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
DIR = os.path.join(HERE, "illust"); os.makedirs(DIR, exist_ok=True)
PICK = os.path.join(DIR, "web_pick.json")          # 検索語 → 選んだファイル
CACHE = os.path.join(DIR, "web_search.json")       # (provider, q, kind) → 候補（1日）
UA = "takken-studio/1.0 (+https://takken.ekunblog.com)"
TOKEN = re.compile(r"\{\{img:([^}|]+?)(?:\|([^}]*))?\}\}")

def _key(name, env):
    v = os.environ.get(env, "").strip()
    if v: return v
    p = os.path.join(ROOT, name)
    return open(p).read().strip() if os.path.exists(p) else ""

def providers(kind="logo"):
    out = []
    if kind == "photo":                                     # 写真はライセンスが明確な所を先に
        if _key(".pexels_api_key", "PEXELS_API_KEY"): out.append("pexels")
        out.append("commons")
    if _key(".brave_api_key", "BRAVE_API_KEY"): out.append("brave")
    if _key(".serpapi_api_key", "SERPAPI_KEY"): out.append("serpapi")
    if kind != "photo": out.append("wiki")
    return out

def _pexels(q, kind, n):
    key = _key(".pexels_api_key", "PEXELS_API_KEY")
    j = _get("https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": q, "per_page": n, "orientation": "landscape", "locale": "ja-JP"}), {"Authorization": key})
    return [{"url": ph["src"]["large2x"], "thumb": ph["src"]["medium"], "title": (ph.get("alt") or "") + f"（Pexels / {ph.get('photographer', '')}）", "page": ph.get("url", ""), "src": "pexels"} for ph in j.get("photos", [])]

def _commons(q, kind, n):
    j = _get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "generator": "search", "gsrsearch": q + " filetype:bitmap", "gsrnamespace": 6, "gsrlimit": n,
                                                                                "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1920, "format": "json"}))
    out = []
    for pg in j.get("query", {}).get("pages", {}).values():
        ii = (pg.get("imageinfo") or [{}])[0]
        if not ii.get("thumburl"): continue
        lic = (ii.get("extmetadata", {}).get("LicenseShortName", {}) or {}).get("value", "")
        out.append({"url": ii["thumburl"], "thumb": ii["thumburl"].replace("/1920px-", "/320px-"), "title": pg.get("title", "").replace("File:", "") + f"（Commons {lic}）", "page": ii.get("descriptionurl", ""), "src": "commons"})
    return out

def _get(url, headers=None, timeout=30, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        return data if binary else json.loads(data.decode("utf-8", "replace"))

def _jload(p, default):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return default

def _jsave(p, obj):
    with open(p + ".tmp", "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)

# ---------------- 候補を探す ----------------
def _brave(q, kind, n):
    key = _key(".brave_api_key", "BRAVE_API_KEY")
    u = "https://api.search.brave.com/res/v1/images/search?" + urllib.parse.urlencode({"q": q, "count": n, "safesearch": "strict", "country": "JP", "search_lang": "ja"})
    j = _get(u, {"Accept": "application/json", "X-Subscription-Token": key})
    return [{"url": r.get("properties", {}).get("url") or r.get("thumbnail", {}).get("src"), "thumb": r.get("thumbnail", {}).get("src"),
             "title": r.get("title", ""), "page": r.get("url", ""), "src": "brave"} for r in j.get("results", []) if r.get("properties", {}).get("url")]

def _serpapi(q, kind, n):
    key = _key(".serpapi_api_key", "SERPAPI_KEY")
    u = "https://serpapi.com/search.json?" + urllib.parse.urlencode({"engine": "google_images", "q": q, "hl": "ja", "gl": "jp", "num": n, "api_key": key, "safe": "active"})
    j = _get(u)
    if j.get("error"): raise RuntimeError(j["error"][:160])
    return [{"url": r.get("original"), "thumb": r.get("thumbnail"), "title": r.get("title", ""), "page": r.get("link", ""), "src": "serpapi"}
            for r in j.get("images_results", [])[:n] if r.get("original")]

def _name(q):
    """「住友不動産 ロゴ」→「住友不動産」(Wikidata で探す名前)"""
    return re.sub(r"\s*(ロゴ|logo|マーク|会社|写真|画像|本社|ビル)\s*$", "", q.strip(), flags=re.I).strip() or q.strip()

def _wd_val(cl, prop):
    for st in cl.get(prop, []):
        v = st.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, str): return v
    return None

def _wiki(q, kind, n):
    name = _name(q); out = []
    # Wikidata: 項目を探して ロゴ(P154) → だめなら 画像(P18)
    j = _get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbsearchentities", "search": name, "language": "ja", "uselang": "ja", "format": "json", "limit": 3}))
    site = None
    def commons(fn, label):
        fp = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(fn.replace(" ", "_"))
        return {"url": fp + "?width=1000", "thumb": fp + "?width=240", "title": label, "page": "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(fn.replace(" ", "_")), "src": "wiki"}
    for ent in j.get("search", [])[:3]:
        c = _get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetclaims", "entity": ent["id"], "format": "json"}))
        cl = c.get("claims", {}); label = ent.get("label", name)
        site = site or _wd_val(cl, "P856")                                   # 公式サイト（アイコン用）
        logo, photo = _wd_val(cl, "P154"), _wd_val(cl, "P18")
        if kind == "logo":
            if logo: out.append(commons(logo, f"{label}（ロゴ）"))
        else:
            if photo: out.append(commons(photo, f"{label}（写真）"))
            if logo: out.append(commons(logo, f"{label}（ロゴ）"))
        if out: break
    # Wikipedia(ja): ロゴなら記事内の画像で名前に logo が入る物、写真なら代表画像
    try:
        if kind == "logo":
            w = _get("https://ja.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "titles": name, "prop": "images", "imlimit": 50, "format": "json", "redirects": 1}))
            for pg in w.get("query", {}).get("pages", {}).values():
                for im in pg.get("images", []):
                    fn = im.get("title", "").split(":", 1)[-1]
                    if re.search(r"logo|ロゴ|mark|emblem", fn, re.I) and not re.search(r"wikipedia|commons|wikidata|edit|question|ambox|crystal", fn, re.I):
                        if all(o["title"] != f"{pg.get('title', name)}（Wikipedia）" for o in out): out.append(commons(fn, f"{pg.get('title', name)}（Wikipedia）"))
        else:
            w = _get("https://ja.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "titles": name, "prop": "pageimages", "pithumbsize": 1000, "format": "json", "redirects": 1}))
            for pg in w.get("query", {}).get("pages", {}).values():
                th = pg.get("thumbnail", {}).get("source")
                if th and all(th != o["url"] for o in out):
                    out.append({"url": th, "thumb": th.replace("/1000px-", "/240px-"), "title": f"{pg.get('title', name)}（Wikipedia）", "page": f"https://ja.wikipedia.org/wiki/{urllib.parse.quote(pg.get('title', name))}", "src": "wiki"})
    except Exception: pass
    # 最後の手: 公式サイトのアイコン（小さいが確実）
    if kind == "logo" and site:
        dom = urllib.parse.urlparse(site).netloc or site
        fav = "https://www.google.com/s2/favicons?" + urllib.parse.urlencode({"domain": dom, "sz": 256})
        out.append({"url": fav, "thumb": fav, "title": f"{name}（サイトのアイコン {dom}）", "page": site, "src": "wiki"})
    return out[:n]

def _rank(res, kind):
    """ロゴ探しの並べ替え: 名前に logo がある・Wikimedia・png/svg を上に、OGP画像・プレスリリース・YouTube アイコンは下に"""
    def score(r):
        u = (r.get("url") or "").lower(); t = (r.get("title") or "").lower(); sc = 0
        if kind == "logo":
            if "logo" in u or "logo" in t or "ロゴ" in t: sc += 5
            if "wikimedia" in u or "wikipedia" in u: sc += 6
            if re.search(r"\.(png|svg)(\?|$)", u): sc += 2
            if re.search(r"ogp|og-image|og_image|release|prtimes|prcdn|youtube|googleusercontent|fbcdn|twimg|instagram|banner|thumb-|_thumb", u): sc -= 4
            if re.search(r"\.jpe?g(\?|$)", u): sc -= 2
        return -sc
    out = []
    for r in sorted(res, key=score):
        m = re.search(r"wikipedia/commons/thumb/\w/\w\w/([^/]+)/", r.get("url") or "")     # Wikimedia の縮小版 → 元ファイルを大きく
        if m:
            fn = m.group(1); fp = "https://commons.wikimedia.org/wiki/Special:FilePath/" + fn
            r = {**r, "url": fp + "?width=1000", "thumb": fp + "?width=240"}
        out.append(r)
    return out

def search(q, kind="logo", n=8, log=None):
    """候補の一覧。鍵のある出どころを順に試し、最初に見つかった所の結果を返す（1日キャッシュ）"""
    q = q.strip(); cache = _jload(CACHE, {}); ck = f"{kind}|{q}"
    hit = cache.get(ck)
    if hit and time.time() - hit.get("t", 0) < 86400 and hit.get("r"): return hit["r"]
    res, errs = [], []
    for p in providers(kind):
        try:
            res = _rank({"brave": _brave, "serpapi": _serpapi, "wiki": _wiki, "pexels": _pexels, "commons": _commons}[p](q, kind, n), kind)
        except Exception as e:
            errs.append(f"{p}: {str(e)[:120]}"); res = []
        if res: break
        errs.append(f"{p}: 0건")
    if log and errs: log("이미지 검색 경고: " + " / ".join(errs))
    if log and res and kind == "photo" and res[0]["src"] in ("brave", "serpapi"): log("※ 사진이 일반 웹 검색에서 왔습니다 (저작권 확인 필요). Pexels 키(.pexels_api_key)를 넣으면 무료 사진을 우선 씁니다")
    if res:
        cache[ck] = {"t": time.time(), "r": res}; _jsave(CACHE, cache)
    return res

# ---------------- 取ってきて PNG にする ----------------
def fetch(url, log=None):
    """URL の画像を illust/web_<md5>.png に保存して、そのパスを返す（失敗は None）"""
    h = hashlib.md5(url.encode()).hexdigest()[:16]; out = os.path.join(DIR, f"web_{h}.png")
    if os.path.exists(out): return out
    try:
        data = _get(url, {"Accept": "image/*,*/*;q=0.8", "Referer": "https://www.google.com/"}, timeout=40, binary=True)
    except Exception as e:
        if log: log(f"이미지 받기 실패: {url[:80]} ({str(e)[:80]})")
        return None
    try:
        if data[:200].lstrip().lower().startswith((b"<svg", b"<?xml")):
            _svg_png(data, out)
        else:
            from PIL import Image
            im = Image.open(io.BytesIO(data)); im.load()
            if im.mode not in ("RGB", "RGBA"): im = im.convert("RGBA")
            if max(im.size) > 1600: im.thumbnail((1600, 1600))
            im.save(out, "PNG")
    except Exception as e:
        if log: log(f"이미지 변환 실패: {url[:80]} ({str(e)[:80]})")
        return None
    return out

def _svg_png(data, out):
    from weasyprint import HTML
    with tempfile.TemporaryDirectory() as td:
        svg = os.path.join(td, "a.svg"); open(svg, "wb").write(data)
        pdf = os.path.join(td, "a.pdf")
        HTML(string=f"<html><head><style>@page{{size:1000px 600px;margin:0}}body{{margin:0}}</style></head>"
                    f"<body><img src='file://{svg}' style='width:1000px;height:600px;object-fit:contain'></body></html>").write_pdf(pdf)
        import subprocess
        subprocess.run(["pdftoppm", "-singlefile", "-png", "-r", "96", pdf, out[:-4]], check=True)

def picks(): return _jload(PICK, {})

def pick(q, path):
    """スタジオで選んだ画像を 検索語 に結びつける"""
    d = picks(); d[q.strip()] = path; _jsave(PICK, d)

def resolve(q, kind="logo", log=None):
    """検索語 → ローカルの PNG（選んであればそれ、なければ候補を上から試す）。見つからなければ None"""
    p = picks().get(q.strip())
    if p and os.path.exists(p): return p
    for c in search(q, kind, 6, log):
        path = fetch(c["url"], log)
        if path:
            pick(q, path); return path
    return None

def resolve_tokens(body, log=None):
    """本文の {{img:…}} を <img> に（取れなかった物は消す）"""
    if not body or "{{img:" not in body: return body
    def rep(m):
        q, opts = m.group(1).strip(), dict(kv.split("=", 1) for kv in (m.group(2) or "").split(",") if "=" in kv)
        kind = opts.get("kind", "photo" if re.search(r"写真|ビル|本社|外観|photo", q) else "logo")
        p = resolve(q, kind, log)
        if not p: return ""
        h = int(opts.get("h", 44)); extra = "max-width:260px;" if kind == "logo" else ""
        return f"<img src='file://{p}' alt='{q}' style='height:{h}px;{extra}vertical-align:middle;margin:0 10px 0 0;object-fit:contain'>"
    return TOKEN.sub(rep, body)

def tokens(body):
    return [m.group(1).strip() for m in TOKEN.finditer(body or "")]

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("q"); ap.add_argument("--kind", default="logo"); ap.add_argument("--get", action="store_true")
    a = ap.parse_args()
    print("providers:", providers())
    for c in search(a.q, a.kind, 6, print): print(" ", c["src"], c["title"][:40], c["url"][:100])
    if a.get: print("→", resolve(a.q, a.kind, print))
