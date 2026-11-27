"""데이터 접근 모듈 — takken_db.json 단일 파일.

모든 읽기/쓰기는 이 모듈을 거친다. 나중에 SQLite로 옮길 때 이 모듈만 교체하면 됨.
"""
import json
import os
import tempfile
import threading
from datetime import date

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "takken_db.json")

ERROR_TAGS = ["知識", "実行エラー", "語彙", "初見"]

_lock = threading.Lock()


def load():
    with open(DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def save(db):
    """원자적 저장: 임시 파일에 쓴 뒤 rename."""
    d = os.path.dirname(DB_PATH)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".takken_db_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=1)
        os.replace(tmp, DB_PATH)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def categories(db):
    return db["meta"]["categories"]


def years(db):
    return sorted({q["year"] for q in db["questions"]})


def subtopics(db):
    return sorted({q["subtopic"] for q in db["questions"] if q.get("subtopic")})


def error_tag_of(q):
    """error_reason 앞머리의 태그를 추출. 없으면 None."""
    reason = q.get("error_reason") or ""
    for t in ERROR_TAGS:
        if reason.startswith(t):
            return t
    return None


def wrong_count(q):
    return len(q.get("wrong_dates") or [])


def filter_questions(db, years=None, cats=None, subtopic=None, min_wrong=0, error_tag=None):
    """복수 연도·복수 분야·細目 부분일치·誤答回数·error_reason 태그로 필터."""
    out = []
    for q in db["questions"]:
        if years and q["year"] not in years:
            continue
        if cats and q["category"] not in cats:
            continue
        if subtopic and subtopic not in (q.get("subtopic") or ""):
            continue
        if wrong_count(q) < min_wrong:
            continue
        if error_tag and error_tag_of(q) != error_tag:
            continue
        out.append(q)
    return out


def find(db, year, number):
    for q in db["questions"]:
        if q["year"] == year and q["number"] == int(number):
            return q
    return None


def add_wrong_dates(year, numbers, d):
    """틀린 번호 일괄 등록. 같은 날짜가 이미 있으면 중복 추가 안 함(재제출 안전).

    반환: (등록된 번호, 이미 등록돼 있던 번호, 존재하지 않는 번호)
    """
    with _lock:
        db = load()
        added, dup, missing = [], [], []
        for n in numbers:
            q = find(db, year, n)
            if q is None:
                missing.append(n)
            elif d in q["wrong_dates"]:
                dup.append(n)
            else:
                q["wrong_dates"].append(d)
                q["wrong_dates"].sort()
                added.append(n)
        if added:
            save(db)
        return added, dup, missing


def record_answer(year, number, correct):
    """다시 풀기 모드: 틀리면 오늘 날짜를 wrong_dates에 추가. 맞으면 아무것도 안 함."""
    if correct:
        return
    with _lock:
        db = load()
        q = find(db, year, number)
        if q is None:
            raise KeyError(f"{year} 問{number} 없음")
        q["wrong_dates"].append(date.today().isoformat())
        save(db)


def record_answers_batch(wrongs):
    """시험 모드 일괄 채점: [(year, number)] 오답 목록에 오늘 날짜를 한 번의 저장으로 추가."""
    if not wrongs:
        return
    today = date.today().isoformat()
    with _lock:
        db = load()
        for year, number in wrongs:
            q = find(db, year, number)
            if q is not None:
                q["wrong_dates"].append(today)
        save(db)


def set_field(year, number, field, value):
    """subtopic / error_reason 등 단일 필드 갱신."""
    assert field in ("subtopic", "error_reason")
    with _lock:
        db = load()
        q = find(db, year, number)
        if q is None:
            raise KeyError(f"{year} 問{number} 없음")
        q[field] = value
        save(db)


def add_year(records, overwrite=False):
    """파서 출력(records)을 DB에 추가. wrong_dates/error_reason 필드를 보충.

    같은 연도가 이미 있으면 overwrite=True일 때만 교체(誤答 기록은 번호가 같으면 보존).
    """
    if not records:
        raise ValueError("문제가 0개 — 스캔본 PDF이거나 형식이 다른 PDF입니다")
    year = records[0]["year"]
    with _lock:
        db = load()
        existing = {q["number"]: q for q in db["questions"] if q["year"] == year}
        if existing and not overwrite:
            raise ValueError(f"연도 {year}는 이미 {len(existing)}문제 등록됨 (덮어쓰기 체크 필요)")
        for r in records:
            old = existing.get(r["number"])
            r.setdefault("subtopic", "")
            r["wrong_dates"] = old["wrong_dates"] if old else []
            r["error_reason"] = old["error_reason"] if old else ""
            if old and old.get("subtopic") and not r["subtopic"]:
                r["subtopic"] = old["subtopic"]
        db["questions"] = [q for q in db["questions"] if q["year"] != year] + records
        db["questions"].sort(key=lambda q: (q["year"], q["number"]))
        save(db)
    return year, len(records)


def reset_wrong(keys):
    """[(year, number)] 목록의 wrong_dates를 비움 (틀린 횟수 초기화). 반환: 초기화된 문제 수."""
    with _lock:
        db = load()
        n = 0
        for year, number in keys:
            q = find(db, year, int(number))
            if q is not None and q["wrong_dates"]:
                q["wrong_dates"] = []
                n += 1
        if n:
            save(db)
        return n


def upsert_questions(records):
    """개별 문제 단위 추가/갱신 (부분 연도 지원 — 스캔본에서 옮긴 오답 문제 등).

    같은 (year, number)가 있으면 문제 텍스트만 갱신하고 오답기록·細目·이유는 보존.
    반환: (추가 수, 갱신 수)
    """
    with _lock:
        db = load()
        by_key = {(q["year"], q["number"]): q for q in db["questions"]}
        added = updated = 0
        for r in records:
            r.setdefault("subtopic", "")
            r.setdefault("subs", [])
            key = (r["year"], int(r["number"]))
            old = by_key.get(key)
            if old:
                r["wrong_dates"] = old["wrong_dates"]
                r["error_reason"] = old["error_reason"]
                if old.get("subtopic") and not r["subtopic"]:
                    r["subtopic"] = old["subtopic"]
                updated += 1
            else:
                r["wrong_dates"] = []
                r["error_reason"] = ""
                added += 1
            by_key[key] = r
        db["questions"] = sorted(by_key.values(), key=lambda q: (q["year"], q["number"]))
        save(db)
        return added, updated


# ---- 통계 ----

def stats_year_category(db):
    """연도 × 분야 정답수 표. {year: {cat: (correct, total)}} + 합계."""
    cats = categories(db)
    table = {}
    for y in years(db):
        row = {}
        for c in cats:
            qs = [q for q in db["questions"] if q["year"] == y and q["category"] == c]
            wrong = sum(1 for q in qs if wrong_count(q) > 0)
            row[c] = (len(qs) - wrong, len(qs))
        total = sum(t for _, t in row.values())
        correct = sum(c for c, _ in row.values())
        row["合計"] = (correct, total)
        table[y] = row
    return table


def stats_subtopics(db):
    """細目별 누적 誤答回数 내림차순. [(subtopic, 누적횟수, 문제수)]"""
    acc = {}
    for q in db["questions"]:
        n = wrong_count(q)
        if n == 0:
            continue
        key = q.get("subtopic") or "（細目未入力）"
        cnt, qn = acc.get(key, (0, 0))
        acc[key] = (cnt + n, qn + 1)
    return sorted(((k, c, qn) for k, (c, qn) in acc.items()), key=lambda x: -x[1])


def stats_error_tags(db):
    """error_reason 태그 비율. [(tag, count)] — 태그 없는 오답은 未分類."""
    acc = {t: 0 for t in ERROR_TAGS}
    acc["未分類"] = 0
    for q in db["questions"]:
        if wrong_count(q) == 0:
            continue
        t = error_tag_of(q)
        acc[t if t else "未分類"] += 1
    return [(k, v) for k, v in acc.items() if v > 0]
