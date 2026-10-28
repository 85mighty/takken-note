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

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def secret(env, fname):
    v = os.environ.get(env)
    if v: return v.strip()
    p = os.path.join(ROOT, fname)
    if os.path.exists(p): return open(p, encoding="utf-8").read().strip()
    sys.exit(f"{env} が未設定です。{p} に保存するか、環境変数で渡してください。")

def call(site, path, auth, method="GET", data=None):
    url = site.rstrip("/") + "/wp-json/wp/v2/" + path
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": "Basic " + auth, "Content-Type": "application/json", "User-Agent": "takken-note-publisher"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:500]
        hint = ""
        if e.code == 401: hint = "\n→ ユーザー名かアプリケーションパスワードが違います（ログイン用パスワードでは通りません）。"
        if e.code == 403: hint = "\n→ そのユーザーに投稿の権限がないか、セキュリティ系プラグインが REST API を止めています。"
        if e.code == 404: hint = "\n→ REST API が無効か、パーマリンク設定が「基本」のままの可能性があります。"
        sys.exit(f"WordPress API エラー {e.code}: {msg}{hint}")

def youtube_embed(url):
    return ('<!-- wp:embed {"url":"%s","type":"video","providerNameSlug":"youtube","responsive":true,"className":"wp-embed-aspect-16-9 wp-has-aspect-ratio"} -->\n'
            '<figure class="wp-block-embed is-type-video is-provider-youtube wp-block-embed-youtube wp-embed-aspect-16-9 wp-has-aspect-ratio">'
            '<div class="wp-block-embed__wrapper">\n%s\n</div></figure>\n<!-- /wp:embed -->') % (url, url)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html"); ap.add_argument("--title", required=True); ap.add_argument("--slug", required=True)
    ap.add_argument("--excerpt", default=""); ap.add_argument("--youtube", default=""); ap.add_argument("--draft", action="store_true")
    ap.add_argument("--site", default="https://takken.ekunblog.com")
    a = ap.parse_args()
    content = open(a.html, encoding="utf-8").read()
    content = content.replace("<!--YOUTUBE_EMBED-->", youtube_embed(a.youtube) if a.youtube else "")
    link = ('<!-- wp:paragraph -->\n<p>▶ この内容は動画でも解説しています：<a href="%s" target="_blank" rel="noopener">YouTube「NIPPONリアル」で見る</a></p>\n<!-- /wp:paragraph -->' % a.youtube) if a.youtube else ""
    content = content.replace("<!--YOUTUBE_LINK-->", link)
    if not a.youtube:   # 動画の案内文だけ残らないように
        content = re.sub(r"<!-- wp:paragraph -->\s*<p>動画でも解説しています。</p>\s*<!-- /wp:paragraph -->\s*", "", content)
    auth = base64.b64encode(f"{secret('WP_USER', '.wp_user')}:{secret('WP_APP_PASSWORD', '.wp_app_password')}".encode()).decode()
    post = {"title": a.title, "content": content, "slug": a.slug, "excerpt": a.excerpt, "status": "draft" if a.draft else "publish"}
    found = call(a.site, "posts?" + urllib.parse.urlencode({"slug": a.slug, "status": "publish,draft,pending,future,private", "context": "edit"}), auth)
    if found:
        res = call(a.site, f"posts/{found[0]['id']}", auth, "POST", post); action = "更新"
    else:
        res = call(a.site, "posts", auth, "POST", post); action = "新規作成"
    print(f"{action}しました（{res['status']}）: {res['link']}")
    if res.get("slug") != a.slug:
        print(f"注意: スラッグが {res.get('slug')} になりました（同じスラッグの固定ページ等があると変わります）。YouTube 概要欄のリンクも合わせてください。")

if __name__ == "__main__":
    main()
