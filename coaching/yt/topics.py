# -*- coding: utf-8 -*-
"""動画テーマの候補 (topics.json)。スタジオの一覧で選んで「台本を作る」を押す。
  python3 topics.py --suggest [--n 8]   … ベンチマーク (伸びている動画の傾向) と作成済みの動画から、Claude が候補を出す
候補の出どころ: chat（チャットで決めたもの）/ ai（Claude の提案）/ manual（スタジオで追加）
"""
import argparse, json, os, sys, time, uuid
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE))
PATH = os.path.join(HERE, "topics.json")
BENCH = os.path.join(ROOT, "coaching", "bench", "out", "summary.md")

def load():
    return json.load(open(PATH, encoding="utf-8")) if os.path.exists(PATH) else {"topics": []}

def save(d):
    with open(PATH + ".tmp", "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(PATH + ".tmp", PATH)

def add(title, why="", source="manual", minutes=10, notes="", refs=None):
    d = load()
    t = {"id": uuid.uuid4().hex[:8], "title": title.strip(), "why": why, "source": source, "minutes": int(minutes or 10),
         "notes": notes, "status": "idea", "spec": "", "created": time.strftime("%Y-%m-%d %H:%M"), "refs": refs or []}
    d["topics"].insert(0, t); save(d); return t

def update(tid, **kw):
    d = load()
    for t in d["topics"]:
        if t["id"] == tid: t.update({k: v for k, v in kw.items() if v is not None}); save(d); return t
    return None

def delete(tid):
    d = load(); d["topics"] = [t for t in d["topics"] if t["id"] != tid]; save(d)

SUGGEST_TOOL = {
    "name": "save_topics",
    "description": "動画テーマの候補を保存する。最後に必ず1回呼ぶ。",
    "strict": True,
    "eager_input_streaming": True,
    "input_schema": {"type": "object", "additionalProperties": False, "required": ["topics"], "properties": {
        "topics": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                   "required": ["title", "why", "minutes", "notes", "refs"],
                   "properties": {"title": {"type": "string", "description": "動画のテーマ（日本語・具体的に）"},
                                  "why": {"type": "string", "description": "なぜ今これか（検索・時期・ベンチマークの根拠）"},
                                  "minutes": {"type": "integer"},
                                  "notes": {"type": "string", "description": "台本で押さえる点"},
                                  "refs": {"type": "array", "items": {"type": "string"},
                                           "description": "参考にしたベンチマーク動画の番号（V1 など）。1〜3個。なければ空"}}}}}},
}

def bench_videos(limit=120):
    """ベンチマークで伸びている動画（チャンネル中央値に対する倍率が高い順）。番号 V1.. をつけて Claude に見せ、
    提案の根拠として番号で返してもらう → 本物のタイトル・再生数・URL に置き換える（URL を AI に書かせない）"""
    import glob, statistics
    rows = []
    for p in glob.glob(os.path.join(ROOT, "coaching", "bench", "out", "videos_*.json")):
        try: ch = json.load(open(p, encoding="utf-8"))
        except ValueError: continue
        if ch.get("self"): continue
        vs = [v for v in ch.get("videos", []) if v.get("view_count")]
        if len(vs) < 5: continue
        med = statistics.median(v["view_count"] for v in vs) or 1
        for v in vs:
            rows.append({"channel": ch.get("name", ""), "title": v.get("title", ""), "views": v["view_count"],
                         "ratio": round(v["view_count"] / med, 1), "date": v.get("upload_date") or "",
                         "url": f"https://www.youtube.com/watch?v={v['id']}"})
    rows.sort(key=lambda r: (r["ratio"], r["views"]), reverse=True)
    top = rows[:limit]
    for r in sorted(rows, key=lambda r: r["views"], reverse=True)[:40]:   # 再生数そのものが多い動画も入れる
        if r not in top: top.append(r)
    for i, r in enumerate(top, 1): r["id"] = f"V{i}"
    return top

def _fmt_views(n):
    return f"{n/10000:.1f}万回" if n >= 10000 else f"{n}回"

def _refs(ids, table):
    by = {r["id"]: r for r in table}
    out = []
    for i in ids or []:
        r = by.get(str(i).strip())
        if r and r not in out: out.append({k: r[k] for k in ("channel", "title", "views", "ratio", "date", "url")})
    return out[:3]

def suggest(n=8, log=print):
    import registry, scriptgen
    reg = registry.load()
    made = "\n".join(f"- {v.get('yt_title') or v.get('label')}" for v in reg["videos"])[:4000]
    bench = open(BENCH, encoding="utf-8").read()[:5000] if os.path.exists(BENCH) else "（ベンチマーク未取得）"
    table = bench_videos()
    vlist = "\n".join(f"{r['id']} | {r['channel']} | {_fmt_views(r['views'])} | 中央値の{r['ratio']}倍 | {r['date']} | {r['title']}" for r in table) or "（なし）"
    queued = "\n".join(f"- {t['title']}" for t in load()["topics"])[:2000]
    user = (f"今日: {time.strftime('%Y-%m-%d')}\nチャンネル「NIPPONリアル」（宅建）の次の動画テーマを {n} 個提案してください。\n"
            f"時期（試験・合格発表・登録講習・申込みの日程）と、他の宅建チャンネルで伸びている傾向を踏まえて。"
            f"必要なら web_search で今の話題や日程を確認する。すでに作った動画・候補と重ならないこと。\n\n"
            f"各候補の refs には、根拠にした下の「伸びている動画」の番号（V1 など）を1〜3個入れる。\n\n"
            f"■ ベンチマーク（伸びている動画の傾向）\n{bench}\n\n■ 伸びている動画（番号 | チャンネル | 再生数 | そのチャンネルの中央値の何倍か | 投稿日 | タイトル）\n{vlist}\n\n■ 作成済みの動画\n{made}\n\n■ すでにある候補\n{queued}")
    if not scriptgen.api_key(False):                        # キーがなければ Claude Code CLI で
        def check(o):
            ts = o.get("topics") if isinstance(o, dict) else None
            return None if isinstance(ts, list) and ts and all(isinstance(t, dict) and isinstance(t.get("title"), str) for t in ts) else "topics が不正です"
        items = scriptgen.cli_json(user, "あなたは宅建 YouTube チャンネルの企画担当です。", SUGGEST_TOOL["input_schema"], check, log)["topics"]
        for t in reversed(items):
            add(t["title"], t.get("why", ""), "ai", t.get("minutes") or 10, t.get("notes", ""), _refs(t.get("refs"), table)); log(f"  ＋ {t['title']}")
        return len(items)
    import anthropic
    client = anthropic.Anthropic(api_key=scriptgen.api_key())
    messages = [{"role": "user", "content": user}]
    for _ in range(6):
        log("… Claude 에 후보 요청 중")
        try:
            with client.messages.stream(model=scriptgen.MODEL, max_tokens=16000, tools=[scriptgen.WEB, SUGGEST_TOOL],
                                        output_config={"effort": "medium"}, messages=messages) as st:
                msg = st.get_final_message()
        except ValueError as e:
            log(f"  입력을 읽지 못해 다시 시도합니다 ({e})"); continue
        if msg.stop_reason == "refusal": raise RuntimeError("Claude 가 제안을 거절했습니다")
        if msg.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": msg.content}); continue
        calls = [b for b in msg.content if b.type == "tool_use" and b.name == "save_topics"]
        if msg.stop_reason == "max_tokens": raise RuntimeError("중간에 끊겼습니다")
        if not calls:
            messages.append({"role": "assistant", "content": msg.content})
            messages.append({"role": "user", "content": "save_topics ツールで保存してください。"}); continue
        items = (calls[0].input or {}).get("topics")
        ok = isinstance(items, list) and items and all(isinstance(t, dict) and isinstance(t.get("title"), str) for t in items)
        if not ok:
            messages.append({"role": "assistant", "content": msg.content})
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": calls[0].id, "is_error": True, "content": "INVALID_INPUT: topics が不正です"}]})
            continue
        for t in reversed(items):
            add(t["title"], t.get("why", ""), "ai", t.get("minutes") or 10, t.get("notes", ""), _refs(t.get("refs"), table))
            log(f"  ＋ {t['title']}")
        return len(items)
    raise RuntimeError("후보를 저장하지 못했습니다")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--suggest", action="store_true"); ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--add"); ap.add_argument("--why", default=""); ap.add_argument("--minutes", type=int, default=10); ap.add_argument("--notes", default="")
    a = ap.parse_args()
    if a.suggest: print(f"후보 {suggest(a.n, log=lambda m: print(m, flush=True))}건 추가했습니다")
    elif a.add: print(add(a.add, a.why, "chat", a.minutes, a.notes))
    else: print(json.dumps(load(), ensure_ascii=False, indent=1)[:3000])
