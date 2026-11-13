# -*- coding: utf-8 -*-
"""WordPress (takken.ekunblog.com) に記事を発行・更新する。
  同じスラッグの記事があれば更新、なければ新規作成するので、何度実行しても記事は1本のまま。

  認証: WordPress の「アプリケーションパスワード」を使う（ログインパスワードではない）
    ~/takken-note/.wp_user          … WordPress のユーザー名
    ~/takken-note/.wp_app_password  … アプリケーションパスワード（スペース入りのままでよい）
    （環境変数 WP_USER / WP_APP_PASSWORD でも可。どちらも git には入れない）

  使い方:
    python3 coaching/blog/publish_wp.py coaching/blog/takken-5mon-menjo.html \
        --title "..." --slug takken-5mon-menjo --excerpt "..." [--youtube https://youtu.be/xxxx] [--draft]
"""
import argparse, base64, json, os, re, sys, urllib.error, urllib.parse, urllib.request

class WPError(Exception): pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def secret(env, fname):
    v = os.environ.get(env)
    if v: return v.strip()
    p = os.path.join(ROOT, fname)
    if os.path.exists(p): return open(p, encoding="utf-8").read().strip()
    raise WPError(f"{env} 가 설정되지 않았습니다. {p} 에 저장하거나 환경변수로 넘겨주세요.")

def call(site, path, auth, method="GET", data=None, raw=None, headers=None, timeout=60):
    url = site.rstrip("/") + "/wp-json/wp/v2/" + path
    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": "Basic " + auth, "Content-Type": "application/json", "User-Agent": "takken-note-publisher", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:500]
        hint = ""
        if e.code == 401: hint = "\n→ 사용자명이나 애플리케이션 비밀번호가 틀립니다 (로그인 비밀번호로는 안 됩니다)."
        if e.code == 403: hint = "\n→ 그 사용자에게 글 작성 권한이 없거나, 보안 플러그인이 REST API 를 막고 있습니다."
        if e.code == 404: hint = "\n→ REST API 가 꺼져 있거나 고유주소 설정이 「기본」일 수 있습니다."
        raise WPError(f"WordPress API 오류 {e.code}: {msg}{hint}")

def youtube_embed(url):
    return ('<!-- wp:embed {"url":"%s","type":"video","providerNameSlug":"youtube","responsive":true,"className":"wp-embed-aspect-16-9 wp-has-aspect-ratio"} -->\n'
            '<figure class="wp-block-embed is-type-video is-provider-youtube wp-block-embed-youtube wp-embed-aspect-16-9 wp-has-aspect-ratio">'
            '<div class="wp-block-embed__wrapper">\n%s\n</div></figure>\n<!-- /wp:embed -->') % (url, url)

SITE = "https://takken.ekunblog.com"

def auth():
    return base64.b64encode(f"{secret('WP_USER', '.wp_user')}:{secret('WP_APP_PASSWORD', '.wp_app_password')}".encode()).decode()

def fill_youtube(content, youtube=""):
    content = content.replace("<!--YOUTUBE_EMBED-->", youtube_embed(youtube) if youtube else "")
    link = ('<!-- wp:paragraph -->\n<p>▶ この内容は動画でも解説しています：<a href="%s" target="_blank" rel="noopener">YouTube「NIPPONリアル」で見る</a></p>\n<!-- /wp:paragraph -->' % youtube) if youtube else ""
    content = content.replace("<!--YOUTUBE_LINK-->", link)
    if not youtube:   # 動画の案内文だけ残らないように
        content = re.sub(r"<!-- wp:paragraph -->\s*<p>動画でも解説しています。</p>\s*<!-- /wp:paragraph -->\s*", "", content)
    return content

def upload_media(path, site=SITE, au=None, want_id=False):
    """画像・音声・PDF をメディアライブラリに上げて URL を返す (同じファイル名があればそれを使う)。want_id なら (id, URL)"""
    au = au or auth()
    fn = os.path.basename(path)
    found = call(site, "media?" + urllib.parse.urlencode({"search": os.path.splitext(fn)[0], "per_page": 5}), au)
    for m in found or []:
        if os.path.splitext(fn)[0] in (m.get("source_url") or ""): return (m["id"], m["source_url"]) if want_id else m["source_url"]
    ctype = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp",
             "mp3": "audio/mpeg", "pdf": "application/pdf"}[fn.rsplit(".", 1)[-1].lower()]
    res = call(site, "media", au, "POST", raw=open(path, "rb").read(), timeout=600,
               headers={"Content-Type": ctype, "Content-Disposition": f'attachment; filename="{fn}"'})
    return (res["id"], res["source_url"]) if want_id else res["source_url"]

def featured_image(youtube="", text_lines=None, name="post", au=None, site=SITE):
    """アイキャッチのメディア ID。動画があればその YouTube サムネイル、なければ文字サムネイル"""
    import thumbs
    path = thumbs.youtube_thumb(youtube) if youtube else None
    if not path and text_lines: path = thumbs.text_thumb(text_lines, name)
    if not path: return None
    try: return upload_media(path, site, au, want_id=True)[0]
    except Exception as e:
        print("  ✗ 썸네일 업로드 실패:", e, flush=True); return None

def publish(content, title, slug, excerpt="", youtube="", draft=False, site=SITE, au=None, featured=None):
    """同じスラッグがあれば更新、なければ新規。(記事URL, 新規作成/更新, 状態, 実際のスラッグ) を返す。featured=アイキャッチのメディア ID"""
    au = au or auth()
    post = {"title": title, "content": fill_youtube(content, youtube), "slug": slug, "excerpt": excerpt, "status": "draft" if draft else "publish",
            "comment_status": "closed", "ping_status": "closed"}
    if featured: post["featured_media"] = featured
    found = call(site, "posts?" + urllib.parse.urlencode({"slug": slug, "status": "publish,draft,pending,future,private", "context": "edit"}), au)
    if found:
        res = call(site, f"posts/{found[0]['id']}", au, "POST", post); action = "갱신"
    else:
        res = call(site, "posts", au, "POST", post); action = "새로 작성"
    return res["link"], action, res["status"], res.get("slug")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html"); ap.add_argument("--title", required=True); ap.add_argument("--slug", required=True)
    ap.add_argument("--excerpt", default=""); ap.add_argument("--youtube", default=""); ap.add_argument("--draft", action="store_true")
    ap.add_argument("--site", default=SITE)
    a = ap.parse_args()
    try:
        link, action, status, slug = publish(open(a.html, encoding="utf-8").read(), a.title, a.slug, a.excerpt, a.youtube, a.draft, a.site)
    except WPError as e:
        sys.exit(str(e))
    print(f"{action} 완료 ({status}): {link}")
    if slug != a.slug:
        print(f"注意: スラッグが {slug} になりました（同じスラッグの固定ページ等があると変わります）。YouTube 概要欄のリンクも合わせてください。")

if __name__ == "__main__":
    main()
