# -*- coding: utf-8 -*-
"""テーマから台本 (spec) を作る。Claude API (Opus 5.5) が必要ならウェブ検索で日程・数字を確かめてから書く。
  python3 scriptgen.py "5問免除の登録講習はいつ申し込むべきか" --minutes 10 [--notes "メモ"] [--name R8_xxx]
  → specs/<name>.json （スタジオの一覧に「台本」として出る）

APIキー: ANTHROPIC_API_KEY か ~/takken-note/.anthropic_api_key （git には入れない）
"""
import argparse, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE))
SPECS = os.path.join(HERE, "specs")
MODEL = os.environ.get("SCRIPTGEN_MODEL", "claude-opus-5-5")

def api_key(required=True):
    if os.environ.get("ANTHROPIC_API_KEY"): return os.environ["ANTHROPIC_API_KEY"].strip()
    p = os.path.join(ROOT, ".anthropic_api_key")
    if os.path.exists(p) and open(p).read().strip(): return open(p).read().strip()
    if required: sys.exit("Claude API 키가 없습니다. ~/takken-note/.anthropic_api_key 에 저장해 주세요.")
    return ""

def claude_cli():
    """API キーがないときに使う VPS の Claude Code CLI (seido-tube と同じ方式)"""
    import shutil
    return shutil.which("claude") or next((p for p in ("/root/.local/bin/claude", "/usr/local/bin/claude") if os.path.exists(p)), None)

def available():
    return bool(api_key(False) or claude_cli())

def cli_json(prompt, system, schema, check, log=print, tries=3):
    """claude -p で JSON を1つ返してもらう。check(obj) がエラー文を返したら、それを伝えてやり直す"""
    import subprocess
    cli = claude_cli()
    if not cli: sys.exit("Claude API 키도 Claude Code CLI 도 없습니다.")
    ask = (prompt + "\n\n# 出力\n次の JSON Schema に合う JSON を ```json ブロックで1つだけ返してください。説明文は不要です。\n"
           + json.dumps(schema, ensure_ascii=False))
    for k in range(tries):
        log(f"… Claude Code CLI 에 요청 중 ({k+1})")
        r = subprocess.run([cli, "-p", "--output-format", "json", "--append-system-prompt", system, "--allowedTools", "WebSearch", "WebFetch"],
                           input=ask, capture_output=True, text=True, timeout=2400)
        if r.returncode != 0: raise RuntimeError("claude CLI 오류: " + (r.stderr or r.stdout)[-500:])
        try: text = json.loads(r.stdout).get("result", "")
        except ValueError: text = r.stdout
        m = re.search(r"```json\s*([\s\S]*?)```", text) or re.search(r"(\{[\s\S]*\})", text)
        try: obj = json.loads(m.group(1)) if m else None
        except ValueError: obj = None
        err = "JSON が読み取れません" if obj is None else check(obj)
        if not err: return obj
        log(f"  형식이 맞지 않아 다시 요청합니다: {err}")
        ask += f"\n\n前回の出力は不正でした（{err}）。スキーマどおりの JSON だけを返してください。"
    raise RuntimeError("Claude Code CLI 에서 올바른 결과를 받지 못했습니다")

SLIDE_GUIDE = """スライドの body は HTML の断片。使えるクラス:
- <div class='key'>一番大事な一文</div>（黄色の強調ボックス。1枚に1つまで）
- <table><tr><th>見出し</th>...</tr><tr><td>...</td></tr></table>（td class='c' 中央寄せ, td class='hi' 赤強調, tr class='now' 黄色行）
- <ul class='steps'><li><b>要点</b>──補足</li></ul>（箇条書き。3〜4項目まで）
- <div class='two'><div>左</div><div>右</div></div>（2列比較）
- <div class='big'>28点<small>説明</small></div>（大きな数字）
- <p class='note'>注記・出典</p>
- 1枚目だけ: <div class='cover'><h2>動画タイトル</h2><h3>サブタイトル</h3><p>※注記</p></div>（title は空にする）
画面は 1920×1080。字幕が下に入るので、1枚に詰め込みすぎない（本文は 120〜220字目安）。上か右にイラストが入る。"""

DESC_GUIDE = """youtube.description は次の形（これまでのチャンネルの書き方）。{{chapters}} {{blog}} {{related}} はそのまま書く（書き出し後に自動で埋まる）:
<動画の要約 2〜3文。誰向けか・何が分かるか>

▼この動画で分かること
・...
・...

▼目次
{{chapters}}

{{blog}}

▼関連動画
{{related}}

#宅建 #宅建士 ...（8〜14個）"""

SYSTEM = f"""あなたは YouTube チャンネル「NIPPONリアル」（宅建士試験の解説・合格発表・制度の解説）の台本作家です。
視聴者は宅建の受験生と、不動産会社で働く人。落ち着いた「です・ます」調で、結論から先に、数字と日付は正確に。
煽り・誇張・断定できないことの断定はしない。分からないことは「〜と案内されています」「公式発表で確認してください」と書く。
日程・費用・合格点などの事実は web_search で公式情報（不動産適正取引推進機構・国交省・講習機関など）を確認してから書く。
読み上げ (speech) は Google の音声合成で読むので、記号や括弧を避け、数字は読みやすく（「問46から問50」）、1文を短く。
speech は画面の body の内容を説明する話し言葉で、1枚 150〜400字。読み上げ速度は1分あたり約260字。

{SLIDE_GUIDE}

{DESC_GUIDE}

illust には、そのスライドのイラストのテーマを日本語で1文（例:「宅建士に合格したら何が変わる？」「宅建試験の合格発表を不安そうに待つ受験生」「不動産を購入するときの重要事項説明」）。人物・気持ち・小物が浮かぶ具体的な場面にする。
blog はブログ記事 (takken.ekunblog.com) 用: slug は英小文字とハイフン、title は検索されやすい日本語。
related には、関連動画の台帳 key を関連が強い順に2〜4個。
最後に必ず save_video ツールで保存する。notes には確認が必要な点・出典URLを書く。"""

SAVE_TOOL = {
    "name": "save_video",
    "description": "完成した動画の台本・YouTube文面・ブログ情報を保存する。台本ができたら必ず1回呼ぶ。",
    "strict": True,
    "eager_input_streaming": True,
    "input_schema": {
        "type": "object", "additionalProperties": False,
        "required": ["name", "label", "slides", "youtube", "blog", "related", "notes"],
        "properties": {
            "name": {"type": "string", "description": "英数字とアンダースコアの ID。例: R8_kousyu"},
            "label": {"type": "string", "description": "スタジオに出す短い日本語名"},
            "slides": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["title", "sub", "body", "speech", "illust"],
                "properties": {"title": {"type": "string"}, "sub": {"type": "string"}, "body": {"type": "string"},
                               "speech": {"type": "string"}, "illust": {"type": "string"}}}},
            "youtube": {"type": "object", "additionalProperties": False, "required": ["title", "description", "tags"],
                        "properties": {"title": {"type": "string"}, "description": {"type": "string"},
                                       "tags": {"type": "array", "items": {"type": "string"}}}},
            "blog": {"type": "object", "additionalProperties": False, "required": ["slug", "title", "excerpt"],
                     "properties": {"slug": {"type": "string"}, "title": {"type": "string"}, "excerpt": {"type": "string"}}},
            "related": {"type": "array", "items": {"type": "string"}},
            "notes": {"type": "string"},
        }},
}
WEB = {"type": "web_search_20260209", "name": "web_search", "max_uses": 8}

def _valid(inp):
    """eager_input_streaming では入力が途中で切れても気づけないので、自分で形を確かめる"""
    if not isinstance(inp, dict): return "入力がオブジェクトではありません"
    for k in ("name", "label", "notes"):
        if not isinstance(inp.get(k), str): return f"{k} がありません"
    sl = inp.get("slides")
    if not isinstance(sl, list) or len(sl) < 3: return "slides が3枚未満です"
    for i, s in enumerate(sl, 1):
        if not isinstance(s, dict) or not all(isinstance(s.get(k), str) for k in ("title", "sub", "body", "speech", "illust")):
            return f"slides[{i}] の項目が欠けています"
        if not s["speech"].strip(): return f"slides[{i}] の speech が空です"
    yt = inp.get("youtube") or {}
    if not (isinstance(yt.get("title"), str) and isinstance(yt.get("description"), str) and isinstance(yt.get("tags"), list)): return "youtube が欠けています"
    bl = inp.get("blog") or {}
    if not all(isinstance(bl.get(k), str) for k in ("slug", "title", "excerpt")): return "blog が欠けています"
    if not isinstance(inp.get("related"), list): return "related がありません"
    return None

def _context():
    """関連動画の台帳と、参考にする既存 spec の1枚"""
    import registry
    reg = registry.load()
    vids = [f"- {v['key']}: {v.get('label') or v.get('yt_title', '')}" for v in reg["videos"] if not v.get("short")][:60]
    ex = ""
    for p in (os.path.join(SPECS, "_archive", "R8_menjo.json"),):
        if os.path.exists(p):
            ex = json.dumps(json.load(open(p, encoding="utf-8"))["slides"][3], ensure_ascii=False)
    return "関連動画の台帳 (key: 名前):\n" + "\n".join(vids) + ("\n\n参考: これまでのスライド1枚の例\n" + ex if ex else "")

def generate(topic, minutes=10, notes="", name=None, log=print):
    n_slides = max(6, round(minutes * 1.4))
    user = (f"テーマ: {topic}\n長さ: 約{minutes}分（スライド {n_slides}枚前後、speech 合計 約{minutes*260}字）\n"
            f"今日の日付: {time.strftime('%Y-%m-%d')}\n" + (f"メモ・方針: {notes}\n" if notes else "") + "\n" + _context())
    if not api_key(False):                                   # キーがなければ Claude Code CLI で
        sysp = SYSTEM.replace("最後に必ず save_video ツールで保存する。", "")
        return save(cli_json(user, sysp, SAVE_TOOL["input_schema"], _valid, log), topic, name)
    import anthropic
    client = anthropic.Anthropic(api_key=api_key())
    messages = [{"role": "user", "content": user}]
    for turn in range(8):
        log(f"… Claude 에 요청 중 ({turn+1})")
        try:
            with client.messages.stream(model=MODEL, max_tokens=64000, system=SYSTEM, tools=[WEB, SAVE_TOOL],
                                        output_config={"effort": "high"}, messages=messages) as st:
                msg = st.get_final_message()
        except ValueError as e:          # ツール入力の JSON が壊れていた → やり直す
            log(f"  입력을 읽지 못해 다시 시도합니다 ({e})"); continue
        for b in msg.content:
            if b.type == "server_tool_use": log(f"  검색: {(b.input or {}).get('query', '')}")
        if msg.stop_reason == "refusal": raise RuntimeError("Claude 가 이 주제의 작성을 거절했습니다")
        if msg.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": msg.content}); continue
        calls = [b for b in msg.content if b.type == "tool_use" and b.name == "save_video"]
        if msg.stop_reason == "max_tokens":
            raise RuntimeError("대본이 너무 길어 중간에 끊겼습니다. 분량을 줄여 다시 해주세요")
        if not calls:
            messages.append({"role": "assistant", "content": msg.content})
            messages.append({"role": "user", "content": "save_video ツールで保存してください。"}); continue
        err = _valid(calls[0].input)
        if err:
            messages.append({"role": "assistant", "content": msg.content})
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": calls[0].id, "is_error": True,
                                                          "content": json.dumps({"INVALID_INPUT": err}, ensure_ascii=False)}]})
            continue
        return save(calls[0].input, topic, name, msg.usage)
    raise RuntimeError("대본을 저장하지 못했습니다 (주고받기 한도)")

def unique_name(base):
    base = re.sub(r"[^A-Za-z0-9_]", "_", base or "") or "R8_video"
    n, k = base, 2
    while os.path.exists(os.path.join(SPECS, n + ".json")) or os.path.exists(os.path.join(SPECS, "_archive", n + ".json")):
        n = f"{base}_{k}"; k += 1
    return n

def save(inp, topic, name=None, usage=None):
    name = unique_name(name or inp["name"])
    spec = {"name": name, "outdir": name.lower(), "label": inp["label"], "status": "script", "topic": topic,
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
            "slides": [{k: s[k] for k in ("title", "sub", "body", "speech", "illust")} for s in inp["slides"]],
            "youtube": {**inp["youtube"], "url": ""}, "blog": {**inp["blog"], "url": ""},
            "related": inp["related"], "notes": inp["notes"]}
    p = os.path.join(SPECS, name + ".json")
    with open(p + ".tmp", "w", encoding="utf-8") as f: json.dump(spec, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)
    print(f"저장: specs/{name}.json  슬라이드 {len(spec['slides'])}장" + (f"  (입력 {usage.input_tokens} / 출력 {usage.output_tokens} 토큰)" if usage else ""), flush=True)
    return name

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("topic"); ap.add_argument("--minutes", type=int, default=10)
    ap.add_argument("--notes", default=""); ap.add_argument("--name"); ap.add_argument("--topic-id"); a = ap.parse_args()
    import topics
    try:
        name = generate(a.topic, a.minutes, a.notes, a.name, log=lambda m: print(m, flush=True))
    except Exception:
        if a.topic_id: topics.update(a.topic_id, status="idea")
        raise
    if a.topic_id: topics.update(a.topic_id, status="done", spec=name)
    print("→ 스튜디오 목록에 「대본」으로 올라왔습니다. 열어서 슬라이드를 확인해 주세요", flush=True)
