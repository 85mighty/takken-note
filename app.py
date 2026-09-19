"""宅建士 오답노트 웹앱 (Flask, 단일 프로세스, localhost 우선)

실행: python3 app.py   →  http://localhost:8788
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import date

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_file, url_for)

import db
import parse_takken

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = "takken-note-local"  # 로컬 1인용 — flash 메시지 전용
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


def read_filters():
    """쿼리스트링 → 필터 dict. 목록/다시풀기/PDF에서 공유."""
    years = request.args.getlist("year")
    cats = request.args.getlist("category")
    subtopic = (request.args.get("subtopic") or "").strip()
    try:
        min_wrong = int(request.args.get("min_wrong", 1))
    except ValueError:
        min_wrong = 1
    error_tag = request.args.get("error_tag") or ""
    return {"years": years, "cats": cats, "subtopic": subtopic,
            "min_wrong": min_wrong, "error_tag": error_tag}


@app.context_processor
def inject_common():
    d = db.load()
    return {"all_years": db.years(d), "all_cats": db.categories(d),
            "all_subtopics": db.subtopics(d), "error_tags": db.ERROR_TAGS,
            "today": date.today().isoformat()}


# ---- B. 오답 목록 / 필터 ----

@app.route("/")
def index():
    f = read_filters()
    d = db.load()
    qs = db.filter_questions(d, years=f["years"], cats=f["cats"],
                             subtopic=f["subtopic"], min_wrong=f["min_wrong"],
                             error_tag=f["error_tag"])
    qs.sort(key=lambda q: (q["year"], q["number"]))
    no_subtopic = sum(1 for q in qs if not q.get("subtopic"))
    return render_template("index.html", questions=qs, f=f,
                           no_subtopic=no_subtopic,
                           wrong_count=db.wrong_count, qs_query=request.query_string.decode())


# ---- C. 다시 풀기 모드 ----

@app.route("/review")
def review():
    f = read_filters()
    d = db.load()
    qs = db.filter_questions(d, years=f["years"], cats=f["cats"],
                             subtopic=f["subtopic"], min_wrong=f["min_wrong"],
                             error_tag=f["error_tag"])
    qs.sort(key=lambda q: (q["year"], q["number"]))
    payload = [{"year": q["year"], "number": q["number"], "category": q["category"],
                "subtopic": q.get("subtopic") or "", "stem": q["stem"],
                "subs": q["subs"], "choices": q["choices"], "answer": q["answer"],
                "wrong": db.wrong_count(q), "error_reason": q.get("error_reason") or ""}
               for q in qs]
    return render_template("review.html", questions_json=json.dumps(payload, ensure_ascii=False),
                           count=len(payload), f=f)


@app.route("/api/answer", methods=["POST"])
def api_answer():
    j = request.get_json(force=True)
    correct = bool(j["correct"])
    db.record_answer(j["year"], int(j["number"]), correct)
    return jsonify(ok=True)


@app.route("/api/grade_batch", methods=["POST"])
def api_grade_batch():
    """시험 모드: 전부 풀고 나서 한 번에 채점. 오답만 wrong_dates에 기록."""
    j = request.get_json(force=True)
    wrongs = [(r["year"], int(r["number"])) for r in j.get("results", []) if not r["correct"]]
    db.record_answers_batch(wrongs)
    return jsonify(ok=True, wrong=len(wrongs))


@app.route("/api/reason", methods=["POST"])
def api_reason():
    j = request.get_json(force=True)
    tag = (j.get("tag") or "").strip()
    memo = (j.get("memo") or "").strip()
    reason = (tag + ("　" + memo if memo else "")) if tag else memo
    db.set_field(j["year"], int(j["number"]), "error_reason", reason)
    return jsonify(ok=True, reason=reason)


@app.route("/api/subtopic", methods=["POST"])
def api_subtopic():
    j = request.get_json(force=True)
    db.set_field(j["year"], int(j["number"]), "subtopic", (j.get("subtopic") or "").strip())
    return jsonify(ok=True)


# ---- D. 통계 ----

@app.route("/stats")
def stats():
    d = db.load()
    return render_template("stats.html",
                           year_cat=db.stats_year_category(d),
                           cats=db.categories(d),
                           subs=db.stats_subtopics(d),
                           tags=db.stats_error_tags(d))


# ---- A. 문제 등록 ----

@app.route("/register")
def register():
    d = db.load()
    counts = {y: sum(1 for q in d["questions"] if q["year"] == y) for y in db.years(d)}
    return render_template("register.html", year_counts=counts)


@app.route("/register/wrong", methods=["POST"])
def register_wrong():
    year = request.form["year"]
    when = request.form.get("date") or date.today().isoformat()
    raw = request.form.get("numbers", "")
    try:
        numbers = sorted({int(t) for t in raw.replace("，", ",").replace(" ", ",").split(",") if t.strip()})
    except ValueError:
        flash("번호는 숫자를 쉼표로 구분해서 입력 (예: 1,2,3,7,14)", "err")
        return redirect(url_for("register"))
    if not numbers:
        flash("틀린 번호가 비어 있음", "err")
        return redirect(url_for("register"))
    added, dup, missing = db.add_wrong_dates(year, numbers, when)
    msg = f"{year} {when}: {len(added)}문제 등록" + (f" — {added}" if added else "")
    if dup:
        msg += f" / 같은 날짜로 이미 등록됨(건너뜀): {dup}"
    if missing:
        msg += f" / DB에 없는 번호: {missing}"
    flash(msg, "ok" if added else "err")
    return redirect(url_for("register"))


@app.route("/register/upload", methods=["POST"])
def register_upload():
    year = (request.form.get("year") or "").strip()
    overwrite = bool(request.form.get("overwrite"))
    f = request.files.get("pdf")
    if not year or not f or not f.filename:
        flash("연도 라벨과 PDF 파일 둘 다 필요", "err")
        return redirect(url_for("register"))
    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as out:
            f.save(out)
        pages = parse_takken.extract_text(tmp)
        qs = parse_takken.parse_questions(pages)
        ans = parse_takken.parse_answers(pages)
    finally:
        os.unlink(tmp)
    records = []
    for n in sorted(qs):
        q = qs[n]
        records.append({"year": year, "number": n, "category": parse_takken.category(n),
                        "subtopic": "", "stem": q["stem"], "subs": q["subs"],
                        "choices": q["choices"], "answer": ans.get(n)})
    if not records:
        flash("문제를 하나도 추출하지 못함 — 스캔본(이미지) PDF이거나 형식이 다른 PDF. OCR은 지원 안 함.", "err")
        return redirect(url_for("register"))
    bad = [r["number"] for r in records if len(r["choices"]) != 4 or r["answer"] is None]
    try:
        db.add_year(records, overwrite=overwrite)
    except ValueError as e:
        flash(str(e), "err")
        return redirect(url_for("register"))
    msg = f"{year}: {len(records)}문제 등록, 정답 {len(ans)}개"
    if bad:
        msg += f" / 확인 필요(선택지≠4 또는 정답 없음): 問{bad}"
    flash(msg, "ok")
    return redirect(url_for("index", year=year, min_wrong=0))


# ---- E. PDF 출력 ----

@app.route("/pdf")
def pdf():
    f = read_filters()
    d = db.load()
    # make_pdf.py는 연도/분야 각 1개만 받으므로, 복수 선택 시 필터한 임시 DB를 만들어 넘긴다.
    # 細目·태그 필터도 임시 DB 방식으로 반영 (그 경우 요약표 모수도 필터 결과 기준이 됨).
    need_temp = (len(f["years"]) > 1 or len(f["cats"]) > 1
                 or f["subtopic"] or f["error_tag"])
    args = [sys.executable, os.path.join(BASE, "make_pdf.py")]
    tmp_db = None
    try:
        if need_temp:
            sub = db.filter_questions(d, years=f["years"], cats=f["cats"],
                                      subtopic=f["subtopic"], min_wrong=0,
                                      error_tag=f["error_tag"])
            fd, tmp_db = tempfile.mkstemp(suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                json.dump({"meta": d["meta"], "questions": sub}, fp, ensure_ascii=False)
            args.append(tmp_db)
        else:
            args.append(db.DB_PATH)
        out = tempfile.mktemp(suffix=".pdf")
        args.append(out)
        if not need_temp and len(f["years"]) == 1:
            args += ["--year", f["years"][0]]
        if not need_temp and len(f["cats"]) == 1:
            args += ["--category", f["cats"][0]]
        args += ["--min-wrong", str(f["min_wrong"])]
        r = subprocess.run(args, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            abort(500, f"make_pdf.py 실패: {r.stderr[-500:]}")
        name = f"takken_note_{date.today().isoformat()}.pdf"
        return send_file(out, as_attachment=True, download_name=name,
                         mimetype="application/pdf")
    finally:
        if tmp_db and os.path.exists(tmp_db):
            os.unlink(tmp_db)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8788, debug=False)
