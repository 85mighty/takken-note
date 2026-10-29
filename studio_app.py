# -*- coding: utf-8 -*-
"""NIPPONリアル スタジオ — 動画の検収パネル + 宅建ベンチマーク（学習サイトとは別ポートの独立アプリ）
  起動: PORT=8789 python3 studio_app.py   （VPS では pm2 の takken-studio）
  パスワード: .studio_password ファイル（なければ .takken_password と同じ）
"""
import os
import sys
from datetime import timedelta

from flask import Flask, redirect, render_template, request, session, url_for

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "coaching", "yt"))
from studio import bp  # noqa: E402

app = Flask(__name__, template_folder=os.path.join(BASE, "templates"))
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=90)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.register_blueprint(bp)


def _secret_key():
    p = os.path.join(BASE, ".studio_secret_key")
    try:
        return open(p, "rb").read()
    except FileNotFoundError:
        k = os.urandom(32)
        with open(p, "wb") as f:
            f.write(k)
        os.chmod(p, 0o600)
        return k


app.secret_key = _secret_key()
PASSWORD = os.environ.get("STUDIO_PASSWORD") or os.environ.get("TAKKEN_PASSWORD") or None


@app.before_request
def require_login():
    if not PASSWORD or request.endpoint in ("login", "static"):
        return
    if session.get("authed"):
        return
    if request.path.startswith("/studio/api/"):
        return {"ok": False, "error": "ログインが必要です"}, 401
    return redirect(url_for("login", next=request.full_path if request.query_string else request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if PASSWORD and request.form.get("password") == PASSWORD:
            session.permanent = True
            session["authed"] = True
            nxt = request.args.get("next") or ""
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("studio.index"))
        error = "パスワードが違います"
    return render_template("studio_login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def root():
    return redirect(url_for("studio.index"))


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8789")), debug=False, threaded=True)
