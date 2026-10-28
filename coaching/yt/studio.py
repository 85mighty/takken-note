# -*- coding: utf-8 -*-
"""検収パネル (/studio) — スライド型動画の確認・修正・書き出し + 宅建ベンチマークの閲覧
  app.py で  from coaching.yt.studio import bp; app.register_blueprint(bp)  … ではなく sys.path 経由で読み込む。
  サイトのログイン (TAKKEN_PASSWORD) がそのまま効く。
"""
import json, os, subprocess, sys, tempfile, threading, time
from flask import Blueprint, abort, jsonify, render_template, request, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SPECS = os.path.join(HERE, "specs")
HIST = os.path.join(SPECS, ".history")
OUT = os.environ.get("YT_OUT", os.path.join(HERE, "out"))
BENCH = os.path.join(ROOT, "coaching", "bench", "out")
PY = sys.executable

bp = Blueprint("studio", __name__, url_prefix="/studio")
JOB = {"proc": None, "name": None, "log": None, "started": None, "rc": None, "kind": None}
LOCK = threading.Lock()

def _spec_path(name):
    if not name.replace("_", "").replace("-", "").isalnum(): abort(404)
    p = os.path.join(SPECS, f"{name}.json")
    if not os.path.exists(p): abort(404)
    return p

def _load(name):
    return json.load(open(_spec_path(name), encoding="utf-8"))

def _outdir(spec):
    return os.path.join(OUT, spec["outdir"])

def _manifest(spec):
    p = os.path.join(_outdir(spec), f"{spec['name']}.manifest.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

def _keys(slides):
    """スライドのキャッシュキー (r8_goukaku.slide_key と同じ計算)。読み込めなければ None"""
    try:
        sys.path.insert(0, HERE)
        import r8_goukaku as G
        return [G.slide_key(s.get("title", ""), s.get("sub", ""), s.get("body", ""), s.get("speech", "")) for s in slides]
    except Exception:
        return [None] * len(slides)

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
        with open(JOB["log"], encoding="utf-8", errors="replace") as f: tail = "".join(f.readlines()[-25:])
    return {"running": running, "name": JOB["name"], "kind": JOB["kind"], "rc": JOB["rc"], "log": tail,
            "elapsed": int(time.time() - JOB["started"]) if JOB["started"] else 0}

# ---------------- pages ----------------
@bp.route("/")
def index():
    items = []
    for f in sorted(os.listdir(SPECS)) if os.path.isdir(SPECS) else []:
        if not f.endswith(".json"): continue
        sp = json.load(open(os.path.join(SPECS, f), encoding="utf-8"))
        man = _manifest(sp)
        items.append({"name": sp["name"], "label": sp.get("label", sp["name"]), "n": len(sp["slides"]),
                      "total": man["total"] if man else None, "built_at": man["built_at"] if man else None})
    bench = os.path.exists(os.path.join(BENCH, "summary.html"))
    return render_template("studio_index.html", items=items, bench=bench)

@bp.route("/v/<name>")
def edit(name):
    sp = _load(name)
    return render_template("studio_edit.html", name=name, label=sp.get("label", name))

@bp.route("/bench")
def bench():
    p = os.path.join(BENCH, "summary.html")
    if not os.path.exists(p):
        return render_template("studio_index.html", items=[], bench=False, bench_missing=True)
    return send_from_directory(BENCH, "summary.html")

@bp.route("/bench/<path:fn>")
def bench_file(fn):
    return send_from_directory(BENCH, fn)

# ---------------- api ----------------
@bp.route("/api/spec/<name>")
def api_spec(name):
    sp = _load(name); man = _manifest(sp); out = _outdir(sp)
    keys = _keys(sp["slides"])
    built = {m["key"]: m for m in (man or {}).get("slides", [])}
    rows = []
    for i, (s, k) in enumerate(zip(sp["slides"], keys), 1):
        m = built.get(k) if k else None
        thumb = f"c_{k}.png" if k and os.path.exists(os.path.join(out, f"c_{k}.png")) else None
        pv = f"pv{i:02d}.png" if os.path.exists(os.path.join(out, f"pv{i:02d}.png")) else None
        rows.append({"state": "built" if (k and os.path.exists(os.path.join(out, f"c_{k}.mp4"))) else "changed",
                     "in_video": bool(m), "start": m["start"] if m else None, "dur": m["dur"] if m else None,
                     "thumb": thumb, "preview": pv})
    video = None
    if man and os.path.exists(os.path.join(out, man["video"])):
        video = {"file": man["video"], "mtime": int(os.path.getmtime(os.path.join(out, man["video"]))), "total": man["total"], "built_at": man["built_at"]}
    return jsonify(spec=sp, rows=rows, video=video, job=_job_state())

@bp.route("/api/spec/<name>", methods=["POST"])
def api_save(name):
    p = _spec_path(name); sp = _load(name)
    slides = (request.get_json(force=True) or {}).get("slides")
    if not isinstance(slides, list) or not slides: return jsonify(ok=False, error="slides が空です"), 400
    clean = []
    for s in slides:
        if not isinstance(s, dict): return jsonify(ok=False, error="形式が不正です"), 400
        clean.append({k: str(s.get(k, "")) for k in ("title", "sub", "body", "speech")})
    os.makedirs(HIST, exist_ok=True)
    with open(os.path.join(HIST, f"{name}-{time.strftime('%Y%m%d-%H%M%S')}.json"), "w", encoding="utf-8") as f:
        json.dump(sp, f, ensure_ascii=False, indent=1)
    sp["slides"] = clean
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(sp, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return jsonify(ok=True, n=len(clean))

@bp.route("/api/preview/<name>/<int:i>", methods=["POST"])
def api_preview(name, i):
    p = _spec_path(name); sp = _load(name)
    s = request.get_json(force=True) or {}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({k: str(s.get(k, "")) for k in ("title", "sub", "body", "speech")}, f, ensure_ascii=False); tmp = f.name
    try:
        r = subprocess.run([PY, os.path.join(HERE, "build_spec.py"), p, "--preview", str(i), "--slide-json", tmp],
                           capture_output=True, text=True, timeout=180, env=_env(), cwd=HERE)
    finally:
        os.unlink(tmp)
    if r.returncode: return jsonify(ok=False, error=(r.stderr or r.stdout)[-800:]), 500
    info = json.loads(r.stdout.strip().splitlines()[-1])
    return jsonify(ok=True, png=info["png"], page_h=info["page_h"], t=int(time.time()))

@bp.route("/api/build/<name>", methods=["POST"])
def api_build(name):
    p = _spec_path(name); sp = _load(name)
    with LOCK:
        st = _job_state()
        if st["running"]: return jsonify(ok=False, error=f"書き出し中です: {st['name']}"), 409
        os.makedirs(_outdir(sp), exist_ok=True)
        log = os.path.join(_outdir(sp), "build.log")
        f = open(log, "w", encoding="utf-8")
        JOB.update(proc=subprocess.Popen([PY, "-u", os.path.join(HERE, "build_spec.py"), p], stdout=f, stderr=subprocess.STDOUT, env=_env(), cwd=HERE),
                   name=name, log=log, started=time.time(), rc=None, kind="build")
    return jsonify(ok=True)

@bp.route("/api/job")
def api_job():
    return jsonify(_job_state())

@bp.route("/api/chapters/<name>")
def api_chapters(name):
    sp = _load(name); man = _manifest(sp)
    if not man: return jsonify(ok=False, error="まだ書き出されていません"), 404
    lines = [f"{int(m['start'])//60:02d}:{int(m['start'])%60:02d} {m['title']}" for m in man["slides"]]
    return jsonify(ok=True, text="\n".join(lines))

@bp.route("/file/<name>/<path:fn>")
def file(name, fn):
    sp = _load(name)
    return send_from_directory(_outdir(sp), fn, conditional=True)
