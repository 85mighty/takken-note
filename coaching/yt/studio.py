# -*- coding: utf-8 -*-
"""スタジオ (/studio) — テーマ選び → 台本 → 下書き動画 → 音声で完成 → YouTube 文面 → ブログ → ショート
  studio_app.py (ポート 8789) から読み込む。重い処理（書き出し・AI・発行）は1つずつ裏で動かし、ログを画面に出す。
"""
import json, os, re, subprocess, sys, tempfile, threading, time
from flask import Blueprint, abort, jsonify, render_template, request, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE))
SPECS = os.path.join(HERE, "specs")
ARCH = os.path.join(SPECS, "_archive")
HIST = os.path.join(SPECS, ".history")
OUT = os.environ.get("YT_OUT", os.path.join(HERE, "out"))
BENCH = os.path.join(ROOT, "coaching", "bench", "out")
ILL = os.path.join(HERE, "illust")
PY = sys.executable
STEPS = [("script", "대본"), ("draft", "초안 영상"), ("voiced", "음성 완성"), ("uploaded", "YouTube"), ("blogged", "블로그")]
SLIDE_KEYS = ("title", "sub", "body", "speech", "illust", "illust_pos", "illust_seed", "illust_off", "short_hook")

bp = Blueprint("studio", __name__, url_prefix="/studio")
JOB = {"proc": None, "name": None, "log": None, "started": None, "rc": None, "kind": None, "label": None}
LOCK = threading.Lock()

# ---------------- helpers ----------------
def _safe(name):
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", name or ""): abort(404)
    return name

def _spec_path(name):
    _safe(name)
    for d in (SPECS, ARCH):
        p = os.path.join(d, f"{name}.json")
        if os.path.exists(p): return p
    abort(404)

def _load(name):
    return json.load(open(_spec_path(name), encoding="utf-8"))

def _write(p, sp):
    with open(p + ".tmp", "w", encoding="utf-8") as f: json.dump(sp, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)

def _outdir(spec):
    return os.path.join(OUT, spec["outdir"])

def _json(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

def _manifest(spec):
    return _json(os.path.join(_outdir(spec), f"{spec['name']}.manifest.json"))

def _draftman(spec):
    return _json(os.path.join(_outdir(spec), f"{spec['name']}.draft.json"))

def _keys(spec):
    """スライドのキャッシュキー (build_spec と同じ計算: イラスト込みの本文)"""
    try:
        import r8_goukaku as G, illust, vkit as V
        V.SUB_STYLE = spec.get("sub_style")
        out = []
        for s in spec["slides"]:
            b = s.get("body", "") if spec.get("illust_off") else illust.inject(s, s.get("body", ""))
            out.append(G.slide_key(s.get("title", ""), s.get("sub", ""), b, s.get("speech", "")))
        return out
    except Exception:
        return [None] * len(spec["slides"])

def _env():
    env = dict(os.environ)
    if not env.get("GOOGLE_TTS_API_KEY"):
        kp = os.path.join(ROOT, ".google_api_key")
        if os.path.exists(kp): env["GOOGLE_TTS_API_KEY"] = open(kp).read().strip()
    return env

def _job_state():
    p = JOB["proc"]
    running = p is not None and p.poll() is None
    if p is not None and not running and JOB["rc"] is None: JOB["rc"] = p.returncode
    tail = ""
    if JOB["log"] and os.path.exists(JOB["log"]):
        with open(JOB["log"], encoding="utf-8", errors="replace") as f: tail = "".join(f.readlines()[-30:])
    return {"running": running, "name": JOB["name"], "kind": JOB["kind"], "label": JOB["label"], "rc": JOB["rc"], "log": tail,
            "elapsed": int(time.time() - JOB["started"]) if JOB["started"] else 0}

def _start(name, kind, label, argv):
    with LOCK:
        st = _job_state()
        if st["running"]: return jsonify(ok=False, error=f"다른 작업이 진행 중입니다 ({st['label']} · {st['name']}). 끝난 뒤에 눌러주세요"), 409
        logdir = os.path.join(OUT, "_jobs"); os.makedirs(logdir, exist_ok=True)
        log = os.path.join(logdir, f"{kind}.log")
        f = open(log, "w", encoding="utf-8")
        JOB.update(proc=subprocess.Popen([PY, "-u"] + argv, stdout=f, stderr=subprocess.STDOUT, env=_env(), cwd=HERE),
                   name=name, kind=kind, label=label, log=log, started=time.time(), rc=None)
    return jsonify(ok=True)

def _keys_status():
    import illust, scriptgen
    return {"tts": bool(os.environ.get("GOOGLE_TTS_API_KEY") or os.path.exists(os.path.join(ROOT, ".google_api_key"))),
            "claude": scriptgen.available(),
            "wp": os.path.exists(os.path.join(ROOT, ".wp_app_password")) or bool(os.environ.get("WP_APP_PASSWORD")),
            "illust": illust.provider()}

def _list(d):
    items = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith(".json") or f.startswith("TMP"): continue
        sp = json.load(open(os.path.join(d, f), encoding="utf-8"))
        man = _manifest(sp)
        items.append({"name": sp["name"], "label": sp.get("label", sp["name"]), "n": len(sp["slides"]), "status": sp.get("status", "script"),
                      "total": man["total"] if man else None, "built_at": man["built_at"] if man else None,
                      "created": sp.get("created_at", ""), "blog": (sp.get("blog") or {}).get("url", "")})
    return items

# ---------------- pages ----------------
@bp.route("/")
def index():
    import topics
    items = sorted(_list(SPECS), key=lambda x: x["created"], reverse=True)
    return render_template("studio_index.html", items=items, archived=_list(ARCH), topics=topics.load()["topics"],
                           steps=STEPS, keys=_keys_status(), bench=os.path.exists(os.path.join(BENCH, "summary.html")))

@bp.route("/v/<name>")
def edit(name):
    sp = _load(name)
    return render_template("studio_edit.html", name=name, label=sp.get("label", name), steps=STEPS,
                           archived=_spec_path(name).startswith(ARCH), keys=_keys_status())

@bp.route("/style")
def style_page():
    import subs
    return render_template("studio_style.html", presets=subs.PRESETS, fonts=list(subs.FONT_CHOICES), slide_fonts=list(subs.SLIDE_FONTS),
                           style=subs.load_style())

@bp.route("/registry")
def registry_page():
    import registry
    return render_template("studio_registry.html", reg=registry.load())

@bp.route("/bench")
def bench():
    if not os.path.exists(os.path.join(BENCH, "summary.html")):
        return render_template("studio_index.html", items=[], archived=[], topics=[], steps=STEPS, keys=_keys_status(), bench=False, bench_missing=True)
    return send_from_directory(BENCH, "summary.html")

@bp.route("/bench/<path:fn>")
def bench_file(fn):
    return send_from_directory(BENCH, fn)

# ---------------- spec ----------------
@bp.route("/api/spec/<name>")
def api_spec(name):
    import illust
    sp = _load(name); man = _manifest(sp); dman = _draftman(sp); out = _outdir(sp)
    keys = _keys(sp)
    built = {m["key"]: m for m in (man or {}).get("slides", [])}
    drafted = {m["key"]: m for m in (dman or {}).get("slides", [])}
    rows = []
    for i, (s, k) in enumerate(zip(sp["slides"], keys), 1):
        m = built.get(k) if k else None
        d = drafted.get(k) if k else None
        thumb = f"c_{k}.png" if k and os.path.exists(os.path.join(out, f"c_{k}.png")) else None
        ip = illust.path_for(s)
        rows.append({"state": "built" if (k and os.path.exists(os.path.join(out, f"c_{k}.mp4"))) else ("draft" if d else "changed"),
                     "in_video": bool(m), "start": m["start"] if m else None, "dur": m["dur"] if m else None,
                     "dstart": d["start"] if d else None, "thumb": thumb, "illust": os.path.basename(ip) if ip else None,
                     "illust_auto": illust.describe({**s, "illust": ""})[:200] if not s.get("illust") else ""})
    def vid(m):
        if m and os.path.exists(os.path.join(out, m["video"])):
            return {"file": m["video"], "mtime": int(os.path.getmtime(os.path.join(out, m["video"]))), "total": m["total"], "built_at": m["built_at"]}
    return jsonify(spec=sp, rows=rows, video=vid(man), draft=vid(dman), job=_job_state())

@bp.route("/api/spec/<name>", methods=["POST"])
def api_save(name):
    p = _spec_path(name); sp = _load(name)
    data = request.get_json(force=True) or {}
    slides = data.get("slides")
    if slides is not None:
        if not isinstance(slides, list) or not slides: return jsonify(ok=False, error="슬라이드가 비어 있습니다"), 400
        clean = []
        for s in slides:
            if not isinstance(s, dict): return jsonify(ok=False, error="형식이 올바르지 않습니다"), 400
            c = {k: str(s.get(k, "")) for k in ("title", "sub", "body", "speech")}
            if s.get("illust"): c["illust"] = str(s["illust"])
            if s.get("illust_pos") in ("top", "right", "none"): c["illust_pos"] = s["illust_pos"]
            if s.get("illust_seed"): c["illust_seed"] = int(s["illust_seed"])
            if s.get("short_hook"): c["short_hook"] = str(s["short_hook"])
            clean.append(c)
        sp["slides"] = clean
    meta = data.get("meta") or {}
    if "label" in meta: sp["label"] = str(meta["label"])[:80]
    if isinstance(meta.get("youtube"), dict):
        yt = sp.setdefault("youtube", {})
        for k in ("title", "description", "url"):
            if k in meta["youtube"]: yt[k] = str(meta["youtube"][k])
        if "tags" in meta["youtube"]:
            t = meta["youtube"]["tags"]
            yt["tags"] = [x.strip() for x in (t.split(",") if isinstance(t, str) else t) if str(x).strip()]
    if isinstance(meta.get("blog"), dict):
        b = sp.setdefault("blog", {})
        for k in ("slug", "title", "excerpt", "url"):
            if k in meta["blog"]: b[k] = str(meta["blog"][k])
    if isinstance(meta.get("related"), list): sp["related"] = [str(x) for x in meta["related"] if str(x).strip()]
    if "illust_off" in meta: sp["illust_off"] = bool(meta["illust_off"])
    if "status" in meta and meta["status"] in [s for s, _ in STEPS]: sp["status"] = meta["status"]
    if isinstance(meta.get("youtube"), dict) and meta["youtube"].get("url"):      # URL は台帳にも入れる（他の動画の関連リンクになる）
        import registry
        reg = registry.load(); registry.upsert(reg, sp["name"], label=sp.get("label"), title=(sp.get("youtube") or {}).get("title"), url=meta["youtube"]["url"]); registry.save(reg)
        order = [s for s, _ in STEPS]
        if order.index(sp.get("status", "script")) < order.index("uploaded"): sp["status"] = "uploaded"
    os.makedirs(HIST, exist_ok=True)
    _write(os.path.join(HIST, f"{name}-{time.strftime('%Y%m%d-%H%M%S')}.json"), _load(name))
    _write(p, sp)
    return jsonify(ok=True, n=len(sp["slides"]))

@bp.route("/api/preview/<name>/<int:i>", methods=["POST"])
def api_preview(name, i):
    p = _spec_path(name)
    s = request.get_json(force=True) or {}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({k: s.get(k, "") for k in SLIDE_KEYS if k in s}, f, ensure_ascii=False); tmp = f.name
    try:
        r = subprocess.run([PY, os.path.join(HERE, "build_spec.py"), p, "--preview", str(i), "--slide-json", tmp],
                           capture_output=True, text=True, timeout=180, env=_env(), cwd=HERE)
    finally:
        os.unlink(tmp)
    if r.returncode: return jsonify(ok=False, error=(r.stderr or r.stdout)[-800:]), 500
    info = json.loads(r.stdout.strip().splitlines()[-1])
    return jsonify(ok=True, png=info["png"], page_h=info["page_h"], t=int(time.time()))

# ---------------- jobs ----------------
@bp.route("/api/run/<name>/<kind>", methods=["POST"])
def api_run(name, kind):
    p = _spec_path(name); a = request.get_json(silent=True) or {}
    if kind == "draft": return _start(name, kind, "초안 영상", ["build_spec.py", p, "--draft"])
    if kind == "build": return _start(name, kind, "음성 완성", ["build_spec.py", p])
    if kind == "illust":
        i = int(a.get("i") or 0)
        return _start(name, kind, f"일러스트{' #'+str(i) if i else ''}", ["build_spec.py", p, "--illust", str(i)])
    if kind == "short":
        i = int(a.get("i") or 0)
        if i < 1: abort(400)
        argv = ["shorts.py", p, str(i)] + (["--hook", str(a["hook"])] if a.get("hook") else [])
        return _start(name, kind, f"쇼츠 #{i}", argv)
    if kind == "blog": return _start(name, kind, "블로그 발행", ["blogify.py", p, "--publish"] + (["--draft"] if a.get("draft") else []))
    abort(404)

@bp.route("/api/job")
def api_job():
    return jsonify(_job_state())

@bp.route("/api/topics", methods=["POST"])
def api_topics():
    import topics
    a = request.get_json(force=True) or {}
    op = a.get("op")
    if op == "add":
        if not (a.get("title") or "").strip(): return jsonify(ok=False, error="주제가 비어 있습니다"), 400
        topics.add(a["title"], a.get("why", ""), "manual", a.get("minutes") or 10, a.get("notes", ""))
    elif op == "update": topics.update(a["id"], **{k: a.get(k) for k in ("title", "why", "minutes", "notes", "status")})
    elif op == "delete": topics.delete(a["id"])
    elif op == "suggest": return _start("topics", "suggest", "AI 주제 후보 찾기", ["topics.py", "--suggest"])
    elif op == "make":
        t = next((x for x in topics.load()["topics"] if x["id"] == a.get("id")), None)
        if not t: abort(404)
        topics.update(t["id"], status="making")
        return _start("topics", "script", f"대본 만들기: {t['title'][:20]}",
                      ["scriptgen.py", t["title"], "--minutes", str(t.get("minutes") or 10), "--notes", t.get("notes", "") + ("\n" + t["why"] if t.get("why") else ""), "--topic-id", t["id"]])
    return jsonify(ok=True, topics=topics.load()["topics"])

# ---------------- YouTube / shorts ----------------
@bp.route("/api/ytext/<name>")
def api_ytext(name):
    import ytext
    return jsonify(ok=True, **ytext.compose(_load(name)))

@bp.route("/api/shorts/<name>")
def api_shorts(name):
    sp = _load(name); d = os.path.join(_outdir(sp), "shorts"); out = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith(".mp4"):
            txt = os.path.join(d, f[:-4] + ".txt")
            out.append({"file": "shorts/" + f, "text": open(txt, encoding="utf-8").read() if os.path.exists(txt) else "",
                        "mtime": int(os.path.getmtime(os.path.join(d, f)))})
    return jsonify(ok=True, shorts=out)

# ---------------- style / registry ----------------
@bp.route("/api/style", methods=["GET", "POST"])
def api_style():
    import subs
    if request.method == "POST":
        st = request.get_json(force=True) or {}
        cur = subs.load_style()
        for k, v in st.items():
            if k in cur or k in ("preset",): cur[k] = v
        for k in ("size", "stroke", "box_radius", "max_chars", "max_lines", "bottom"):
            if k in cur: cur[k] = int(cur[k])
        cur["box_alpha"] = float(cur.get("box_alpha", 0.6)); cur["box"] = bool(cur.get("box")); cur["shadow"] = bool(cur.get("shadow"))
        if request.args.get("save") == "1": subs.save_style(cur)
        d = os.path.join(OUT, "_style"); os.makedirs(d, exist_ok=True)
        fn = f"sample_{int(time.time()*1000)}.png"
        for old in os.listdir(d):
            if old.startswith("sample_"): os.remove(os.path.join(d, old))
        bg = next((os.path.join(r, f) for r, _ds, fs in os.walk(OUT) for f in fs if f.startswith("c_") and f.endswith(".png")), None)
        subs.sample(os.path.join(d, fn), cur, bg)
        return jsonify(ok=True, sample=fn, style=cur)
    return jsonify(subs.load_style())

@bp.route("/style/sample/<fn>")
def style_sample(fn):
    return send_from_directory(os.path.join(OUT, "_style"), _safe(fn.replace(".png", "")) + ".png")

@bp.route("/api/registry", methods=["GET", "POST"])
def api_registry():
    import registry
    if request.method == "GET": return jsonify(registry.load())
    a = request.get_json(force=True) or {}
    if a.get("op") == "fetch": return _start("registry", "fetch", "YouTube URL 가져오기", ["registry.py", "--fetch"])
    reg = registry.load()
    for row in a.get("videos") or []:
        if row.get("key"):
            registry.upsert(reg, row["key"], label=row.get("label"), url=(row.get("url") or "").strip(),
                            match=[w for w in (row.get("match") or "").split() if w] if isinstance(row.get("match"), str) else None)
    registry.save(reg)
    return jsonify(ok=True)

# ---------------- files ----------------
@bp.route("/file/<name>/<path:fn>")
def file(name, fn):
    sp = _load(name)
    return send_from_directory(_outdir(sp), fn, conditional=True, as_attachment=request.args.get("dl") == "1")

@bp.route("/illust/<fn>")
def illust_file(fn):
    if not re.fullmatch(r"[0-9a-f]{16}\.(png|jpg|svg)", fn): abort(404)
    return send_from_directory(ILL, fn)
