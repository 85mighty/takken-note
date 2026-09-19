# 宅建 오답노트

宅建士(일본 부동산거래사) 과거문제 오답노트 개인용 웹앱. 상세 요구사항은 `takken-note-spec.md`.

## 실행

```bash
pip install flask pdfplumber weasyprint
python3 app.py
# → http://localhost:8788
```

PDF 출력에는 일본어 폰트가 필요: `apt-get install fonts-noto-cjk` (Noto Sans CJK JP).

PM2로 상시 실행할 경우:

```bash
pm2 start "python3 app.py" --name takken-note --cwd /path/to/takken-note
```

## 화면

| 경로 | 기능 |
|---|---|
| `/` | 오답 목록 + 필터(연도·분야 복수선택, 細目 부분일치, 誤答≥N, 이유 태그) + 細目 인라인 편집 |
| `/review?...&mode=instant` | 바로 풀기 — 선택지 클릭 즉시 채점, 틀리면 오늘 날짜 자동 기록 |
| `/review?...&mode=exam` | 시험 모드 — 다 풀고 「채점하기」로 일괄 채점·기록, 결과는 인쇄 가능 |
| `/stats` | 細目별 누적 誤答(가장 중요), 연도×분야 정답수, 이유 태그 비율 |
| `/register` | 틀린 번호 일괄 등록(재풀이 누적), 새 연도 PDF 업로드·파싱 |
| `/pdf?...` | 현재 필터 그대로 오답노트 PDF 다운로드 (`make_pdf.py`) |

목록 화면의 필터가 「바로 풀기 / 시험 모드 / PDF 출력」 버튼에 그대로 이어진다.
아이폰·아이패드 대응(터치 타깃 확대, 좁은 화면 레이아웃).

## 새 연도 추가 절차

1. `/register` → 「새 연도 PDF 추가」에 연도 라벨(예: `R5`)과 텍스트형 과거문제 PDF 업로드
   - 정답표 형식은 2가지 자동 인식: `問N` 헤더형(R7식), 숫자 그리드형(R6식)
   - 스캔본(이미지) PDF는 파싱 불가 — 에러만 표시 (OCR 미지원)
2. 업로드 직후 목록(誤答≥0 필터)으로 이동됨 → 노란 줄(細目 미입력)을 표에서 바로 입력
3. 문제를 풀고 `/register` → 「틀린 번호 등록」에 번호 입력 (같은 연도 재풀이도 동일, 횟수 누적)

CLI로도 가능:

```bash
python3 parse_takken.py R5_question_answer.pdf R5 r5.json
python3 -c "import json, db; db.add_year(json.load(open('r5.json')))"
```

## 데이터

- `takken_db.json` 단일 파일이 전체 DB (git으로 이력 관리). 스키마는 spec 참조
- 모든 읽기/쓰기는 `db.py` 경유 — 나중에 SQLite로 옮길 때 이 모듈만 교체
- `wrong_dates` 길이 = 틀린 횟수. `error_reason`은 `태그　메모` 형식 (태그: 知識/実行エラー/語彙/初見)

## 파일

| 파일 | 내용 |
|---|---|
| `app.py` | Flask 웹앱 (포트 8788) |
| `db.py` | 데이터 접근 모듈 |
| `parse_takken.py` | 과거문제 PDF → JSON 파서 |
| `make_pdf.py` | DB → 오답노트 PDF (WeasyPrint) |
| `takken_db.json` | 문제·오답 DB |
| `R6_question_answer.pdf` | R6 원본 문제 PDF (파서 검증용 원본) |
| `R7_question_answer.pdf` | ※ 원본이 아니라 `make_pdf.py`로 생성한 오답노트 PDF 샘플 |
