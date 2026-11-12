# -*- coding: utf-8 -*-
"""スタジオ (/studio) — テーマ選び → 台本 → 下書き動画 → 音声で完成 → YouTube 文面 → ブログ → ショート
  studio_app.py (ポート 8789) から読み込む。重い処理（書き出し・AI・発行）は1つずつ裏で動かし、ログを画面に出す。
"""
import glob, json, os, re, subprocess, sys, tempfile, threading, time
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
SLIDE_KEYS = ("title", "sub", "body", "speech", "illust", "illust_pos", "illust_seed", "illust_off", "photo", "short_hook", "short_desc", "overlays", "_orig")
OV_KEYS = {"x": float, "y": float, "w": float, "h": float, "size": float, "radius": float, "opacity": float, "pad": float, "stroke": float, "lh": float,
           "text": str, "color": str, "bg": str, "border": str, "align": str, "stroke_color": str, "bold": bool, "img": str,
           "border_left": str, "border_right": str, "border_top": str, "border_bottom": str, "box": bool}

def _clean_ov(ovs):
    out = []
    for o in ovs if isinstance(ovs, list) else []:
        if not isinstance(o, dict): continue
        c = {}
        for k, t in OV_KEYS.items():
            if k in o and o[k] is not None:
                try: c[k] = t(o[k])
                except (TypeError, ValueError): pass
        if c.get("img") and not (os.path.realpath(c["img"]).startswith(ILL) and os.path.exists(c["img"])): c.pop("img")
        if str(c.get("text", "")).strip() or c.get("img") or c.get("box"): out.append(c)
    return out

bp = Blueprint("studio", __name__, url_prefix="/studio")
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
            import build_spec
            out.append(G.slide_key(s.get("title", ""), s.get("sub", ""), build_spec.compose_body(spec, s), s.get("speech", "")))
        return out
    except Exception:
        return [None] * len(spec["slides"])

def _env():
    env = dict(os.environ)
    if not env.get("GOOGLE_TTS_API_KEY"):
        kp = os.path.join(ROOT, ".google_api_key")
        if os.path.exists(kp): env["GOOGLE_TTS_API_KEY"] = open(kp).read().strip()
    return env

JOBDIR = os.path.join(OUT, "_jobs")
CUR = os.path.join(JOBDIR, "current.json")

def _alive(pid):
    try: os.kill(pid, 0); return True
    except OSError: return False

def _job_state():
    """作業の状態。作業は別セッションで動かし current.json に記録するので、スタジオが再起動しても追える"""
    j = _json(CUR) or {}
    if not j: return {"running": False, "name": None, "kind": None, "label": None, "rc": None, "log": "", "elapsed": 0}
    rcf = j["log"] + ".rc"
    rc = int(open(rcf).read().strip() or -1) if os.path.exists(rcf) else None
    running = rc is None and _alive(j["pid"])
    if rc is None and not running: rc = -9          # 結果を書かずに止まった（サーバー再起動など）
    tail = ""
    if os.path.exists(j["log"]):
        with open(j["log"], encoding="utf-8", errors="replace") as f: tail = "".join(f.readlines()[-30:])
    if rc == -9: tail += "\n※ 작업이 중간에 멈췄습니다 (서버 재시작 등). 다시 눌러주세요."
    end = os.path.getmtime(rcf) if os.path.exists(rcf) else time.time()
    return {"running": running, "name": j["name"], "kind": j["kind"], "label": j["label"], "rc": rc, "log": tail,
            "elapsed": int((end if not running else time.time()) - j["started"]), "topic": j.get("topic")}

def _start(name, kind, label, argv, topic=None, raw=False):
    import shlex
    with LOCK:
        st = _job_state()
        if st["running"]: return jsonify(ok=False, error=f"다른 작업이 진행 중입니다 ({st['label']} · {st['name']}). 끝난 뒤에 눌러주세요"), 409
        os.makedirs(JOBDIR, exist_ok=True)
        log = os.path.join(JOBDIR, f"{kind}.log")
        if os.path.exists(log + ".rc"): os.remove(log + ".rc")
        # 裏で切り離して動かす（スタジオが再起動・再デプロイされても作業は止まらない）
        q = shlex.quote
        cmd = f"( {shlex.join(argv if raw else [PY, '-u'] + argv)}; echo $? > {q(log + '.rc')} ) > {q(log)} 2>&1 < /dev/null & echo $!"
        r = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, env=_env(), cwd=HERE, start_new_session=True)
        _write(CUR, {"pid": int(r.stdout.strip()), "name": name, "kind": kind, "label": label, "log": log, "started": time.time(), "topic": topic})
    return jsonify(ok=True)

def _keys_status():
    import illust, scriptgen
    return {"tts": bool(os.environ.get("GOOGLE_TTS_API_KEY") or os.path.exists(os.path.join(ROOT, ".google_api_key"))),
            "claude": scriptgen.available(),
            "wp": os.path.exists(os.path.join(ROOT, ".wp_app_password")) or bool(os.environ.get("WP_APP_PASSWORD")),
            "illust": illust.provider(), "illust_choice": illust.chosen(), "illust_avail": illust.providers(),
            "img": __import__("imgsearch").providers()}

def _cover(spec, man, dman):
    """一覧用のサムネイル: 自作サムネ → 完成の1枚目 → 下書きの1枚目"""
    out = _outdir(spec)
    if os.path.exists(os.path.join(out, "thumbnail.png")): return "thumbnail.png"
    for m in (man, dman):
        for sl in (m or {}).get("slides", [])[:1]:
            if sl.get("thumb") and os.path.exists(os.path.join(out, sl["thumb"])): return sl["thumb"]
    return None

def _shorts_of(spec, reg=None):
    """この動画から切り出したショート (out/<outdir>/shorts/*.mp4) と、その題名・概要欄・URL"""
    import registry
    reg = reg or registry.load()
    d = os.path.join(_outdir(spec), "shorts"); out = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith(".mp4") or f.endswith("_raw.mp4") or f.endswith("_cover_tmp.mp4"): continue
        base = os.path.join(d, f[:-4]); txt = open(base + ".txt", encoding="utf-8").read() if os.path.exists(base + ".txt") else ""
        m = re.search(r"【タイトル】\n(.+)", txt); title = m.group(1).strip() if m else f[:-4]
        m = re.search(r"【概要欄】\n(.+)", txt); desc = m.group(1).strip() if m else ""
        m = re.search(r"_s(\d+)$", f[:-4]); slide = int(m.group(1)) if m else None
        poster = base + "_poster.jpg"
        if not os.path.exists(poster):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.3", "-i", base + ".mp4", "-frames:v", "1", "-vf", "scale=360:-2", poster], check=False)
        key = f"{spec['name']}_{f[:-4].split('_')[-1]}" if slide else f[:-4]
        v = registry.get(reg, key) or {}
        tpng = base + "_thumb.png"
        out.append({"file": "shorts/" + f, "poster": "shorts/" + os.path.basename(poster) if os.path.exists(poster) else None, "text": txt,
                    "thumb": "shorts/" + os.path.basename(tpng) if os.path.exists(tpng) else None, "base": f[:-4],
                    "title": title, "desc": desc, "slide": slide, "key": key, "url": v.get("url", ""),
                    "mtime": int(os.path.getmtime(base + ".mp4")), "dur": _dur(base + ".mp4")})
    return out

def _dur(p):
    try:
        import vkit as V; return round(V.dur(p))
    except Exception: return None

def _list(d, reg=None):
    import registry
    reg = reg or registry.load()
    items = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith(".json") or f.startswith("TMP"): continue
        try: sp = json.load(open(os.path.join(d, f), encoding="utf-8"))
        except Exception as e:                                      # 壊れた spec は印を付けて並べる（一覧全体は落とさない）
            items.append({"name": f[:-5], "label": f"⚠ {f} 읽기 실패: {e}", "n": 0, "status": "script", "total": None, "built_at": None, "created": "", "blog": "", "broken": True,
                          "thumb": None, "url": "", "shorts": [], "is_short": False, "short_target": None, "related": []}); continue
        man = _manifest(sp); dman = _draftman(sp); v = registry.get(reg, sp["name"]) or {}
        items.append({"name": sp["name"], "label": sp.get("label", sp["name"]), "n": len(sp["slides"]), "status": sp.get("status", "script"),
                      "total": man["total"] if man else None, "built_at": man["built_at"] if man else None,
                      "created": sp.get("created_at", ""), "blog": (sp.get("blog") or {}).get("url", ""),
                      "url": (sp.get("youtube") or {}).get("url") or v.get("url", ""), "thumb": _cover(sp, man, dman),
                      "is_short": bool(sp.get("short_target")), "short_target": sp.get("short_target"),
                      "video": (man or {}).get("video") if man and os.path.exists(os.path.join(_outdir(sp), man.get("video", ""))) else None,
                      "shorts": _shorts_of(sp, reg) if not sp.get("short_target") else [], "related": sp.get("related") or [], "archived": d == ARCH})
    return items

def _labels(reg=None):
    """動画名 → 表示名（spec / URL 台帳のどちらにあっても引ける）"""
    import registry
    reg = reg or registry.load(); lab = {}
    for v in reg["videos"]: lab[v["key"]] = v.get("label") or v.get("yt_title") or v["key"]
    for d in (SPECS, ARCH):
        for f in os.listdir(d) if os.path.isdir(d) else []:
            if f.endswith(".json") and not f.startswith("TMP"):
                try: sp = json.load(open(os.path.join(d, f), encoding="utf-8")); lab[sp["name"]] = sp.get("label", sp["name"])
                except Exception: pass
    return lab

# ---------------- pages ----------------
@bp.route("/")
def index():
    """롱폼 목록. 쇼츠용 spec (short_target 있음) 은 쇼츠 탭에"""
    import registry
    reg = registry.load()
    items = sorted(_list(SPECS, reg) + _list(ARCH, reg), key=lambda x: x["created"], reverse=True)
    longs = [x for x in items if not x["is_short"]]
    urls = {x["name"]: x["url"] for x in items}
    return render_template("studio_index.html", items=longs, steps=STEPS, labels=_labels(reg), urls=urls, keys=_keys_status())

@bp.route("/shorts")
def shorts_page():
    """쇼츠 탭: 本編(롱폼)별로 묶어서. 쇼츠 전용 spec 도 본편 아래에"""
    import registry
    reg = registry.load()
    items = sorted(_list(SPECS, reg) + _list(ARCH, reg), key=lambda x: x["created"], reverse=True)
    by = {x["name"]: x for x in items}
    groups = []
    for x in items:
        if x["is_short"]: continue
        specs = [y for y in items if y["is_short"] and y["short_target"] == x["name"]]
        groups.append({"long": x, "shorts": x["shorts"], "short_specs": specs})
    orphan = [y for y in items if y["is_short"] and y["short_target"] not in by]
    uploaded = [v for v in reg["videos"] if v.get("short") and v.get("url") and not v.get("parent")]
    return render_template("studio_shorts.html", groups=groups, orphan=orphan, uploaded=uploaded, labels=_labels(reg), keys=_keys_status())

@bp.route("/topics")
def topics_page():
    """주제 후보・벤치마크・학습 자료 블로그 (만들기 전 단계)"""
    import topics, glob
    bfiles = glob.glob(os.path.join(BENCH, "videos_*.json"))
    bench_at = time.strftime("%Y-%m-%d %H:%M", time.localtime(max(os.path.getmtime(f) for f in bfiles))) if bfiles else ""
    sys.path.insert(0, os.path.join(ROOT, "coaching", "blog"))
    import study_posts
    st = study_posts.state()
    study = [{"slug": p["slug"], "title": p["title"], "url": (st.get(p["slug"]) or {}).get("url", ""), "at": (st.get(p["slug"]) or {}).get("at", "")}
             for p in study_posts.posts()]
    return render_template("studio_topics.html", bench_at=bench_at, study=study, topics=topics.load()["topics"], keys=_keys_status(),
                           bench=os.path.exists(os.path.join(BENCH, "summary.html")))

@bp.route("/v/<name>")
def edit(name):
    sp = _load(name)
    tgt = sp.get("short_target")
    return render_template("studio_edit.html", name=name, label=sp.get("label", name), steps=STEPS, short_target=tgt,
                           short_target_label=_labels().get(tgt, tgt) if tgt else None,
                           archived=_spec_path(name).startswith(ARCH), keys=_keys_status())

@bp.route("/scripts")
def scripts_page():
    """AI で作った台本の一覧（トークンを使ったものを後から開き直せる）"""
    rows = []
    for d, arch in ((SPECS, False), (ARCH, True)):
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if not f.endswith(".json") or f.startswith("TMP"): continue
            sp = json.load(open(os.path.join(d, f), encoding="utf-8"))
            u = sp.get("usage") or {}
            rows.append({"name": sp["name"], "label": sp.get("label", sp["name"]), "topic": sp.get("topic", ""), "n": len(sp["slides"]),
                         "chars": sum(len(x.get("speech", "")) for x in sp["slides"]), "created": sp.get("created_at", ""),
                         "status": sp.get("status", "script"), "yt": (sp.get("youtube") or {}).get("title", ""), "url": (sp.get("youtube") or {}).get("url", ""),
                         "tokens": (f"{u['input']:,} / {u['output']:,}" if u.get("input") else ("CLI" if u.get("model") == "claude-code-cli" else "")),
                         "arch": arch, "notes": sp.get("notes", "")})
    rows.sort(key=lambda r: r["created"], reverse=True)
    return render_template("studio_scripts.html", rows=rows, steps=dict(STEPS))

@bp.route("/style")
def style_page():
    import subs, themes
    return render_template("studio_style.html", presets=subs.PRESETS, fonts=list(subs.FONT_CHOICES), slide_fonts=list(subs.SLIDE_FONTS),
                           style=subs.load_style(), themes=[{"key": k, **{x: v[x] for x in ("label", "desc", "font")}} for k, v in themes.THEMES.items() if not v.get("hidden")])

@bp.route("/style/theme/<key>.png")
def style_theme_sample(key):
    """テーマの見本（表＋表紙）。themes.py が新しくなっていれば描き直す"""
    import themes
    if key not in themes.THEMES: abort(404)
    d = os.path.join(OUT, "_style"); os.makedirs(d, exist_ok=True); fn = f"theme_{key}.png"; p = os.path.join(d, fn)
    if not os.path.exists(p) or os.path.getmtime(p) < os.path.getmtime(themes.__file__): themes.sample(key, p)
    return send_from_directory(d, fn, max_age=0)

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
        thumb = f"c_{k}.png" if k and os.path.exists(os.path.join(out, f"c_{k}.png")) else (f"p_{k}.png" if k and os.path.exists(os.path.join(out, f"p_{k}.png")) else None)
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
            if s.get("short_desc"): c["short_desc"] = str(s["short_desc"])
            ov = _clean_ov(s.get("overlays"))
            if ov: c["overlays"] = ov
            if s.get("illust_off"): c["illust_off"] = True
            if isinstance(s.get("_orig"), dict): c["_orig"] = {k: str(s["_orig"].get(k, "")) for k in ("title", "sub", "body", "illust_pos")}
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
    if "motion_off" in meta: sp["motion_off"] = bool(meta["motion_off"])
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
    s = {k: s.get(k, "") for k in SLIDE_KEYS if k in s}
    if "overlays" in s: s["overlays"] = _clean_ov(s["overlays"])
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False); tmp = f.name
    try:
        r = subprocess.run([PY, os.path.join(HERE, "build_spec.py"), p, "--preview", str(i), "--slide-json", tmp],
                           capture_output=True, text=True, timeout=180, env=_env(), cwd=HERE)
    finally:
        os.unlink(tmp)
    if r.returncode: return jsonify(ok=False, error=(r.stderr or r.stdout)[-800:]), 500
    info = json.loads(r.stdout.strip().splitlines()[-1])
    return jsonify(ok=True, png=info["png"], page_h=info["page_h"], t=int(time.time()))

@bp.route("/api/illust_gen/<name>/<int:i>", methods=["POST"])
def api_illust_gen(name, i):
    """配置エディタから絵を1枚作る（その場で待つ。10〜40秒）。作った絵は overlay(img) として置く"""
    import illust
    p = _spec_path(name); sp = _load(name); a = request.get_json(force=True) or {}
    if illust.provider() == "none": return jsonify(ok=False, error="일러스트 키가 없습니다 (.gemini_api_key 등)"), 400
    if i < 1 or i > len(sp["slides"]): abort(404)
    s = dict(sp["slides"][i - 1]); s.pop("illust_off", None); s.pop("illust_pos", None)
    s["illust"] = str(a.get("prompt") or s.get("illust") or "").strip()
    if a.get("new"): s["illust_seed"] = int(time.time())
    try:
        path = illust.ensure(s)
    except Exception as e:
        return jsonify(ok=False, error=str(e)[:400]), 500
    if not path: return jsonify(ok=False, error="그림이 만들어지지 않았습니다"), 500
    sl = sp["slides"][i - 1]; sl["illust"] = s["illust"]
    if "illust_seed" in s: sl["illust_seed"] = s["illust_seed"]
    _write(p, sp)
    return jsonify(ok=True, path=path, file=os.path.basename(path), prompt=s["illust"])

@bp.route("/api/imgsearch")
def api_imgsearch():
    """実在の画像（ロゴ・写真）の候補。?q=住友不動産 ロゴ&kind=logo"""
    import imgsearch
    q = (request.args.get("q") or "").strip(); kind = request.args.get("kind") or "logo"
    if not q: return jsonify(ok=False, error="검색어가 없습니다"), 400
    msgs = []
    try: res = imgsearch.search(q, kind, 8, msgs.append)
    except Exception as e: return jsonify(ok=False, error=str(e)[:300]), 500
    return jsonify(ok=True, results=res, providers=imgsearch.providers(), warn=" / ".join(msgs))

@bp.route("/api/imgpick", methods=["POST"])
def api_imgpick():
    """候補の1つを取ってきて PNG に。{q, url} → {path, file}。q があれば本文の {{img:q}} もこの画像になる"""
    import imgsearch
    a = request.get_json(force=True) or {}; url = a.get("url") or ""; q = (a.get("q") or "").strip()
    if not url: return jsonify(ok=False, error="url 이 없습니다"), 400
    msgs = []; path = imgsearch.fetch(url, msgs.append)
    if not path: return jsonify(ok=False, error="이미지를 받지 못했습니다: " + " / ".join(msgs)), 500
    if q: imgsearch.pick(q, path)
    return jsonify(ok=True, path=path, file=os.path.basename(path))

@bp.route("/api/explode/<name>/<int:i>", methods=["POST"])
def api_explode(name, i):
    """自動レイアウトの要素を1つずつ動かせる overlay にばらす（保存はしない。返ったスライドをエディタで使う）"""
    p = _spec_path(name)
    s = request.get_json(force=True) or {}
    s = {k: s.get(k, "") for k in SLIDE_KEYS if k in s}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False); tmp = f.name
    try:
        r = subprocess.run([PY, os.path.join(HERE, "build_spec.py"), p, "--explode", str(i), "--slide-json", tmp],
                           capture_output=True, text=True, timeout=180, env=_env(), cwd=HERE)
    finally:
        os.unlink(tmp)
    if r.returncode: return jsonify(ok=False, error=(r.stderr or r.stdout)[-800:]), 500
    return jsonify(ok=True, slide=json.loads(r.stdout.strip().splitlines()[-1]))

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
    if kind == "short_auto":
        n = max(1, min(3, int(a.get("n") or 1)))
        return _start(name, "short", f"쇼츠 (AI가 핵심 장면 선택 ×{n})", ["short_pick.py", p, "--n", str(n)])
    if kind == "reslice":
        argv = ["reslice.py", p, "--sec", str(float(a.get("sec") or 25))] + (["--slide", str(int(a["i"]))] if a.get("i") else [])
        return _start(name, kind, f"AI로 나누기{' #'+str(a['i']) if a.get('i') else ' (전체)'}", argv)
    if kind == "blog": return _start(name, kind, "블로그 발행", ["blogify.py", p, "--publish"] + (["--draft"] if a.get("draft") else []))
    abort(404)

@bp.route("/api/job")
def api_job():
    return jsonify(_job_state())

@bp.route("/api/job/stop", methods=["POST"])
def api_job_stop():
    """実行中の作業を止める（プロセスグループごと）"""
    import signal
    j = _json(CUR) or {}
    if not j: return jsonify(ok=False, error="실행 중인 작업이 없습니다"), 404
    pid = int(j["pid"]); killed = False
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try: os.killpg(os.getpgid(pid), sig); killed = True
        except (ProcessLookupError, PermissionError): pass
        try: os.kill(pid, sig); killed = True
        except (ProcessLookupError, PermissionError): pass
        subprocess.run(["pkill", f"-{int(sig)}", "-P", str(pid)], capture_output=True)
        time.sleep(0.5)
        if not _alive(pid): break
    with open(j["log"] + ".rc", "w") as f: f.write("-15")
    with open(j["log"], "a", encoding="utf-8") as f: f.write("\n※ 사용자가 중지했습니다\n")
    return jsonify(ok=True, killed=killed)

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
    elif op == "study": return _start("study", "study", "학습 자료 블로그 발행", [os.path.join(ROOT, "coaching", "blog", "study_posts.py")])
    elif op == "bench": return _start("bench", "bench", "벤치마크 수집·분석", ["bash", os.path.join(ROOT, "coaching", "bench", "run_bench.sh")], raw=True)
    elif op == "make":
        t = next((x for x in topics.load()["topics"] if x["id"] == a.get("id")), None)
        if not t: abort(404)
        topics.update(t["id"], status="making")
        return _start("topics", "script", f"대본 만들기: {t['title'][:20]}", topic=t["id"], argv=
                      ["scriptgen.py", t["title"], "--minutes", str(t.get("minutes") or 10), "--notes", t.get("notes", "") + ("\n" + t["why"] if t.get("why") else ""), "--topic-id", t["id"]])
    return jsonify(ok=True, topics=topics.load()["topics"])

# ---------------- thumbnail ----------------
@bp.route("/api/thumb/<name>", methods=["GET", "POST"])
def api_thumb(name):
    """롱폼 썸네일 (thumbnail.png) / ?short=<key> 로 쇼츠 썸네일 (shorts/<key>_thumb.png, 9:16)"""
    import thumb
    p = _spec_path(name); sp = _load(name); out = _outdir(sp)
    a = (request.get_json(silent=True) or {}) if request.method == "POST" and "file" not in request.files else {}
    short = request.args.get("short") or a.get("short") or request.form.get("short")
    if short:
        short = _safe(short); sp_ = thumb.short_paths(sp, short)
        tp, hist_dir, rel, histrel = sp_["png"], os.path.join(out, "shorts", sp_["hist"]), f"shorts/{short}_thumb.png", f"shorts/{sp_['hist']}/"
        cfg0 = (sp.get("thumb_shorts") or {}).get(short) or {}
    else:
        tp, hist_dir, rel, histrel = os.path.join(out, "thumbnail.png"), os.path.join(out, "thumb_hist"), "thumbnail.png", "thumb_hist/"
        cfg0 = sp.get("thumb") or {}
    if request.method == "POST":
        if "file" in request.files:                                   # 自分で作った画像を使う (ChatGPT など)
            from PIL import Image
            im = Image.open(request.files["file"].stream).convert("RGB")
            tw = 1080 if short else 1280
            im = im.resize((tw, round(im.height * tw / im.width))) if im.width != tw else im
            os.makedirs(os.path.dirname(tp), exist_ok=True); im.save(tp)
            if short:
                sp.setdefault("thumb_shorts", {}).setdefault(short, {})["custom"] = True; _write(p, sp)
                if os.path.exists(sp_["mp4"]) and request.form.get("cover", "1") == "1": thumb.apply_cover(sp_["mp4"], tp, sp_["raw"])
            else:
                sp.setdefault("thumb", {})["custom"] = True; _write(p, sp)
        elif a.get("restore") and short:                               # ショートの先頭サムネを外して元に戻す
            if os.path.exists(sp_["raw"]): os.replace(sp_["raw"], sp_["mp4"])
        elif a.get("use"):                                              # 履歴から選び直す
            src = os.path.join(hist_dir, _safe(os.path.basename(a["use"])))
            if not os.path.exists(src): abort(404)
            import shutil; shutil.copyfile(src, tp)
            if short and os.path.exists(sp_["mp4"]) and cfg0.get("cover", True): thumb.apply_cover(sp_["mp4"], tp, sp_["raw"])
        else:
            lines = [str(x) for x in (a.get("lines") or []) if str(x).strip()]
            if not lines: return jsonify(ok=False, error="문구를 넣어주세요"), 400
            cfg = {"lines": lines, "style": a.get("style") or "navy", "mode": a.get("mode") or "plain", "badge": (a.get("badge") or "").strip(),
                   "points": [str(x).strip() for x in (a.get("points") or []) if str(x).strip()][:3], "person": a.get("person") or "woman",
                   "quality": a.get("quality") if a.get("quality") in ("medium", "high", "low") else "medium", "use_refs": bool(a.get("use_refs", True)),
                   "provider": a.get("provider") if a.get("provider") in ("replicate", "openai", "auto") else "auto", "cover": bool(a.get("cover", True)),
                   "preset": a.get("preset") if a.get("preset") in thumb.PRESETS else "guide", "model": a.get("model") if a.get("model") in dict(thumb.MODEL_CHOICES) else "gpt-image-2"}
            if short: sp.setdefault("thumb_shorts", {})[short] = cfg
            else: sp["thumb"] = cfg
            _write(p, sp)
            if cfg["mode"] in ("ai", "ai_bg"):                       # 画像生成は 30〜90 秒かかるので裏の作業に
                return _start(name, "thumb", "쇼츠 썸네일 (AI)" if short else "썸네일 (AI)", ["thumb.py", p, "--ai"] + (["--short", short] if short else []))
            thumb.make_plain(sp, cfg, short) if short else thumb.make(sp, lines, cfg["style"], tp)
        sp = _load(name); cfg0 = ((sp.get("thumb_shorts") or {}).get(short) if short else sp.get("thumb")) or {}
    hist = sorted(glob.glob(os.path.join(hist_dir, "*.png")), key=os.path.getmtime, reverse=True)[:8]
    res = {"ok": True, "thumb": cfg0, "suggest": thumb.suggest_short(sp, short) if short else thumb.suggest(sp), "openai": bool(thumb._key()), "providers": thumb.providers(),
           "hist": [{"file": histrel + os.path.basename(h), "mtime": int(os.path.getmtime(h))} for h in hist], "refs": len(thumb.references(sp, vert=bool(short))),
           "covered": bool(short and os.path.exists(sp_["raw"])), "presets": [[k, v["label"]] for k, v in thumb.PRESETS.items()], "models": thumb.MODEL_CHOICES}
    if not os.path.exists(tp): return jsonify(file=None, **res)
    return jsonify(file=rel, mtime=int(os.path.getmtime(tp)), **res)

# ---------------- YouTube / shorts ----------------
@bp.route("/api/ytext/<name>")
def api_ytext(name):
    import ytext
    return jsonify(ok=True, **ytext.compose(_load(name)))

@bp.route("/api/shorts/<name>")
def api_shorts(name):
    sp = _load(name)
    return jsonify(ok=True, shorts=_shorts_of(sp))

@bp.route("/api/short_url", methods=["POST"])
def api_short_url():
    """ショートをアップロードしたら URL を台帳に (key = <本編名>_sNN, parent = 本編名)"""
    import registry
    a = request.get_json(force=True) or {}
    name, key, url, title = _safe(a.get("name", "")), str(a.get("key", "")), (a.get("url") or "").strip(), a.get("title") or ""
    if not key.startswith(name): abort(400)
    if url and not re.match(r"https://(youtu\.be|(www\.)?youtube\.com)/", url): return jsonify(ok=False, error="YouTube URL 을 넣어주세요"), 400
    reg = registry.load(); registry.upsert(reg, key, label=title or None, url=url, short=True, parent=name); registry.save(reg)
    return jsonify(ok=True)

# ---------------- style / registry ----------------
@bp.route("/api/illust_provider", methods=["POST"])
def api_illust_provider():
    import illust
    illust.set_provider((request.get_json(force=True) or {}).get("provider", "auto"))
    return jsonify(ok=True, provider=illust.provider(), choice=illust.chosen())

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
