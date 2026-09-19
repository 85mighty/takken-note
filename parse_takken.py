"""宅建 過去問PDF → JSON パーサ
使い方: python3 parse_takken.py <pdf> <year_label> <out.json>
"""
import re, sys, json
import pdfplumber

CATEGORY = [
    (1, 14, "権利関係"),
    (15, 22, "法令上の制限"),
    (23, 25, "税その他"),
    (26, 45, "宅建業法"),
    (46, 50, "免除科目"),
]

def category(n):
    for a, b, c in CATEGORY:
        if a <= n <= b:
            return c
    return "不明"

def extract_text(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            pages.append(t)
    return pages

NOISE = re.compile(r"^(AB\.indd|—\s*\d+\s*—|\s*\d+\s*$|以下の【問 46】|受理された方は)")

def scrub(s):
    s = re.sub(r"\(cid:\d+\)", "", s)
    s = re.sub(r"A?A?B?B?\.\.?i+n+d+d+.*$", "", s)   # フッター混入
    s = re.sub(r"AB\.indd.*$", "", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()

def clean_lines(text):
    out = []
    for ln in text.split("\n"):
        ln = ln.rstrip()
        if not ln.strip():
            continue
        if NOISE.search(ln.strip()):
            continue
        ln = scrub(ln)
        if ln:
            out.append(ln)
    return out

Q_HEAD = re.compile(r"^【問\s*(\d+)】\s*(.*)$")
CHOICE = re.compile(r"^([1-4])\s+(.*)$")
SUB = re.compile(r"^([アイウエオ])\s+(.*)$")

def parse_questions(pages):
    body = "\n".join(pages)
    lines = clean_lines(body)
    qs = {}
    cur = None
    mode = None  # 'stem' | 'sub' | 'choice'
    for ln in lines:
        m = Q_HEAD.match(ln)
        if m:
            n = int(m.group(1))
            cur = {"number": n, "stem": m.group(2), "subs": [], "choices": []}
            qs[n] = cur
            mode = "stem"
            continue
        if cur is None:
            continue
        m = CHOICE.match(ln)
        if m and (mode in ("stem", "sub", "choice")):
            # 選択肢番号は昇順に来るはず
            expect = len(cur["choices"]) + 1
            if int(m.group(1)) == expect:
                cur["choices"].append(m.group(2))
                mode = "choice"
                continue
        m = SUB.match(ln)
        if m and mode in ("stem", "sub"):
            cur["subs"].append(m.group(1) + "　" + m.group(2))
            mode = "sub"
            continue
        # continuation line
        if mode == "stem":
            cur["stem"] += ln
        elif mode == "sub":
            cur["subs"][-1] += ln
        elif mode == "choice":
            cur["choices"][-1] += ln
    return qs

def parse_answers(pages):
    """最終ページの正解表: 問N行の次行に数字が並ぶ形式"""
    txt = "\n".join(pages[-3:])
    txt = txt.replace("１", "1").replace("２", "2").replace("３", "3").replace("４", "4")
    ans = {}
    lines = txt.split("\n")
    for i, ln in enumerate(lines):
        nums = re.findall(r"問\s*([０-９\d]+)", ln)
        if len(nums) >= 5 and i + 1 < len(lines):
            digits = re.findall(r"[1-4]", lines[i + 1])
            if len(digits) == len(nums):
                for q, d in zip(nums, digits):
                    q = int(q.translate(str.maketrans("０１２３４５６７８９", "0123456789")))
                    ans[q] = int(d)
    if not ans:
        ans = parse_answers_grid(pages)
    return ans


def parse_answers_grid(pages):
    """フォールバック: 問Nヘッダなしの数字グリッド正解表 (R6形式)。
    最終3ページから 1-4 の数字だけの行を集め、行優先で問1..問Nに割り当てる。
    """
    for txt in reversed(pages[-3:]):
        t = txt.replace("１", "1").replace("２", "2").replace("３", "3").replace("４", "4")
        digits = ""
        for ln in t.split("\n"):
            s = re.sub(r"\s+", "", ln)
            if s and re.fullmatch(r"[1-4]+", s):
                digits += s
        if len(digits) >= 40:  # 50問の正解表とみなす
            return {i + 1: int(d) for i, d in enumerate(digits)}
    return {}

def main():
    pdf_path, year, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pages = extract_text(pdf_path)
    qs = parse_questions(pages)
    ans = parse_answers(pages)
    records = []
    for n in sorted(qs):
        q = qs[n]
        # 細目は空欄（後で手動/LLMで付与）
        records.append({
            "year": year,
            "number": n,
            "category": category(n),
            "subtopic": "",
            "stem": q["stem"],
            "subs": q["subs"],
            "choices": q["choices"],
            "answer": ans.get(n),
        })
    bad = [r["number"] for r in records if len(r["choices"]) != 4 or r["answer"] is None]
    print(f"questions: {len(records)}  answers: {len(ans)}  problems: {bad}")
    json.dump(records, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
