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

def add(title, why="", source="manual", minutes=10, notes=""):
    d = load()
    t = {"id": uuid.uuid4().hex[:8], "title": title.strip(), "why": why, "source": source, "minutes": int(minutes or 10),
         "notes": notes, "status": "idea", "spec": "", "created": time.strftime("%Y-%m-%d %H:%M")}
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
                   "required": ["title", "why", "minutes", "notes"],
                   "properties": {"title": {"type": "string", "description": "動画のテーマ（日本語・具体的に）"},
                                  "why": {"type": "string", "description": "なぜ今これか（検索・時期・ベンチマークの根拠）"},
                                  "minutes": {"type": "integer"},
                                  "notes": {"type": "string", "description": "台本で押さえる点"}}}}}},
}

def suggest(n=8, log=print):
    import anthropic, registry, scriptgen
    client = anthropic.Anthropic(api_key=scriptgen.api_key())
    reg = registry.load()
    made = "\n".join(f"- {v.get('yt_title') or v.get('label')}" for v in reg["videos"])[:4000]
    bench = open(BENCH, encoding="utf-8").read()[:6000] if os.path.exists(BENCH) else "（ベンチマーク未取得）"
    queued = "\n".join(f"- {t['title']}" for t in load()["topics"])[:2000]
    user = (f"今日: {time.strftime('%Y-%m-%d')}\nチャンネル「NIPPONリアル」（宅建）の次の動画テーマを {n} 個提案してください。\n"
            f"時期（試験・合格発表・登録講習・申込みの日程）と、他の宅建チャンネルで伸びている傾向を踏まえて。"
            f"必要なら web_search で今の話題や日程を確認する。すでに作った動画・候補と重ならないこと。\n\n"
            f"■ ベンチマーク（伸びている動画の傾向）\n{bench}\n\n■ 作成済みの動画\n{made}\n\n■ すでにある候補\n{queued}")
    messages = [{"role": "user", "content": user}]
    for _ in range(6):
        log("… Claude に候補を依頼中")
        try:
            with client.messages.stream(model=scriptgen.MODEL, max_tokens=16000, tools=[scriptgen.WEB, SUGGEST_TOOL],
                                        output_config={"effort": "medium"}, messages=messages) as st:
                msg = st.get_final_message()
        except ValueError as e:
            log(f"  入力が読み取れませんでした。再試行します ({e})"); continue
        if msg.stop_reason == "refusal": raise RuntimeError("Claude が提案を断りました")
        if msg.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": msg.content}); continue
        calls = [b for b in msg.content if b.type == "tool_use" and b.name == "save_topics"]
        if msg.stop_reason == "max_tokens": raise RuntimeError("途中で切れました")
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
            add(t["title"], t.get("why", ""), "ai", t.get("minutes") or 10, t.get("notes", ""))
            log(f"  ＋ {t['title']}")
        return len(items)
    raise RuntimeError("候補を保存できませんでした")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--suggest", action="store_true"); ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--add"); ap.add_argument("--why", default=""); ap.add_argument("--minutes", type=int, default=10); ap.add_argument("--notes", default="")
    a = ap.parse_args()
    if a.suggest: print(f"候補 {suggest(a.n, log=lambda m: print(m, flush=True))}件 を追加しました")
    elif a.add: print(add(a.add, a.why, "chat", a.minutes, a.notes))
    else: print(json.dumps(load(), ensure_ascii=False, indent=1)[:3000])
