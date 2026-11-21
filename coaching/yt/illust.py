# -*- coding: utf-8 -*-
"""スライドのイラスト。スライドの内容（または指定した説明）から、いらすとや風の絵を作って illust/ に保存する。
  python3 illust.py specs/R8_menjo.json            … 絵がないスライドだけ作る
  python3 illust.py specs/R8_menjo.json --only 3   … 3枚目だけ作り直す (seed を1つ進める)
  python3 illust.py --check                         … 使える作り方（キー）を表示

spec のスライドに書けるもの:
  "illust": "絵の説明（日本語でよい）"  … 空なら タイトル＋本文 から自動で作る
  "illust_off": true                    … このスライドは絵なし
  "illust_pos": "auto" | "top" | "right" … auto: 上に置いて、本文が入りきらなければ右に置く
  "illust_seed": 2                      … 同じ説明で別の絵にしたいとき

作り方 (ILLUST_PROVIDER か、キーがあるもの順):
  gemini … Gemini の画像生成 (GEMINI_API_KEY か .gemini_api_key)。いらすとや風に一番近い
  openai … gpt-image (OPENAI_API_KEY か .openai_api_key)
  claude … Claude が SVG で描く (ANTHROPIC_API_KEY か .anthropic_api_key)
  none   … 作らない
絵の主人公をそろえたいときは illust/_ref.png を置くと（gemini のみ）同じ人物で描く。
"""
import argparse, base64, hashlib, html, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DIR = os.path.join(HERE, "illust"); os.makedirs(DIR, exist_ok=True)

# 画像生成のプロンプト（{theme} にスライドのテーマが入る）
TEMPLATE = """以下のテーマに基づいて、日本の教育資料や解説ブログで使われるような、親しみやすい2Dイラストを1枚生成してください。

【テーマ】
{theme}

【イラストスタイル】
・日本のフリー素材サイトで見かけるような、親しみやすくシンプルな2Dイラスト
・かわいらしいデフォルメ人物
・丸みのある輪郭、自然で豊かな表情
・柔らかいパステルカラー
・手描き風の温かみがあるデジタルイラスト
・シンプルで清潔感のあるフラットデザイン
・軽い水彩風の質感と控えめな陰影
・複雑すぎない構図で、一目でテーマが伝わる

【構図】
・中央にテーマに関連する人物を配置
・周囲に内容を象徴する小物やアイコンを2〜4個配置
・人物の感情が表情やポーズから伝わるようにする
・背景は白、または非常に薄い単色
・余白を十分に確保する
・ブログ記事の冒頭や解説動画のスライドに適した構図

【重要条件】
・文字や文章を入れない
・ロゴや透かしを入れない
・写実的、3D、写真風にしない
・過度に派手な装飾を避ける
・複数の画像を並べたコラージュにしない
・横長16:9の高解像度画像
・シリーズ全体で統一感のあるデザイン"""

def _key(name, env):
    if os.environ.get(env): return os.environ[env].strip()
    p = os.path.join(ROOT, name)
    return open(p).read().strip() if os.path.exists(p) else ""

def providers():
    return {"gemini": bool(_key(".gemini_api_key", "GEMINI_API_KEY")),
            "openai": bool(_key(".openai_api_key", "OPENAI_API_KEY")),
            "claude": bool(_key(".anthropic_api_key", "ANTHROPIC_API_KEY"))}

SETTING = os.path.join(HERE, "illust_provider.txt")      # スタジオで選んだ生成元 (gemini / openai / claude / auto)

def set_provider(name):
    with open(SETTING, "w") as f: f.write(name if name in ("gemini", "openai", "claude", "auto") else "auto")

def chosen():
    p = os.environ.get("ILLUST_PROVIDER")
    if p: return p
    try: return open(SETTING).read().strip() or "auto"
    except OSError: return "auto"

def provider():
    av = providers()
    c = chosen()
    if c in av and av[c]: return c
    return next((k for k in ("gemini", "openai", "claude") if av[k]), "none")

def plain(htm):
    t = re.sub(r"<br\s*/?>|</(li|p|div|h\d|tr)>", "\n", htm or "")
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n\s*\n+", "\n", t).strip()

def describe(s):
    """スライドからテーマを作る（指定があればそれ）"""
    if s.get("illust"): return s["illust"].strip()
    title = (s.get("title") or "").replace("｜", "：").strip()
    body = plain(s.get("body", "")).replace("\n", " ")
    return (f"宅建（宅地建物取引士）試験の解説動画「{title}」の場面。内容: {body}" if title else f"宅建（宅地建物取引士）試験の解説動画の表紙。内容: {body}")[:300]

def prompt_for(s):
    return TEMPLATE.format(theme=describe(s))

def key_for(s):
    return hashlib.md5(repr((prompt_for(s), s.get("illust_seed", 0))).encode()).hexdigest()[:16]

def path_for(s):
    """作ってある絵のパス（なければ None）"""
    if s.get("illust_off"): return None
    k = key_for(s)
    for ext in (".png", ".jpg", ".svg"):
        p = os.path.join(DIR, k + ext)
        if os.path.exists(p): return p
    return None

class Exhausted(Exception):
    """何度待っても 429 → この生成元は今回はもう使わない"""

def _post(url, body, headers, timeout=300, tries=3):
    """429（呼びすぎ）や 5xx は待ってやり直す（20s→40s）。それでもだめなら Exhausted。4xx は応答本文つきで失敗"""
    import time, urllib.error
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = ""
            try: detail = json.loads(e.read().decode("utf-8", "replace")).get("error", {}).get("message", "")[:200]
            except Exception: pass
            if e.code not in (429, 500, 502, 503, 504): raise RuntimeError(f"HTTP {e.code}: {detail or e.reason}")
            if k == tries - 1: raise Exhausted(f"HTTP {e.code} 가 계속됩니다 ({detail or '할당량 초과'})")
            ra = e.headers.get("Retry-After")
            wait = int(ra) if ra and ra.isdigit() else 20 * 2 ** k
            print(f"    … {e.code} 잠시 대기 {wait}초 후 재시도 ({k+1}/{tries-1}) {detail[:80]}", flush=True)
            time.sleep(wait)

DOWN = set()   # この実行でだめだった生成元

PACE = float(os.environ.get("ILLUST_PACE", "7"))     # 画像APIを続けて呼ぶ間隔（秒）。短いと 429 になる

def gen_gemini(prompt, out):
    model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    parts = [{"text": prompt}]
    ref = os.path.join(DIR, "_ref.png")
    if os.path.exists(ref):
        parts.append({"text": "Use the same character design and drawing style as this reference image:"})
        parts.append({"inline_data": {"mime_type": "image/png", "data": base64.b64encode(open(ref, "rb").read()).decode()}})
    d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
              {"contents": [{"parts": parts}],
               "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}},
              {"x-goog-api-key": _key(".gemini_api_key", "GEMINI_API_KEY")})
    for c in d.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            data = (p.get("inlineData") or p.get("inline_data") or {}).get("data")
            if data:
                _save_raster(base64.b64decode(data), out); return out + ".png"
    raise RuntimeError("Gemini 가 이미지를 돌려주지 않았습니다: " + json.dumps(d, ensure_ascii=False)[:300])

def gen_openai(prompt, out):
    hdr = {"Authorization": "Bearer " + _key(".openai_api_key", "OPENAI_API_KEY")}
    model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
    try:
        d = _post("https://api.openai.com/v1/images/generations", {"model": model, "prompt": prompt, "size": "1536x1024", "quality": "medium", "n": 1}, hdr)
    except RuntimeError as e:
        if model != "dall-e-3" and "HTTP 4" in str(e):          # gpt-image が使えない鍵 → dall-e-3 で
            print(f"    {model} 불가 ({str(e)[:100]}) → dall-e-3 로", flush=True)
            d = _post("https://api.openai.com/v1/images/generations", {"model": "dall-e-3", "prompt": prompt[:3900], "size": "1792x1024", "response_format": "b64_json", "n": 1}, hdr)
        else: raise
    _save_raster(base64.b64decode(d["data"][0]["b64_json"]), out); return out + ".png"

SVG_SYSTEM = ("You draw illustrations as standalone SVG code. Style: Japanese free clip-art 'irasutoya' — flat pastel fills, "
              "thin dark-brown (#5a4636) outlines with round joins, cute characters with round heads and dot eyes, soft blush, "
              "simple props. Transparent background. viewBox='0 0 1600 900'. Never draw any text, letters or numbers. "
              "Reply with only the <svg>...</svg> element.")

def gen_claude(prompt, out):
    import anthropic
    client = anthropic.Anthropic(api_key=_key(".anthropic_api_key", "ANTHROPIC_API_KEY"))
    with client.messages.stream(model=os.environ.get("ILLUST_CLAUDE_MODEL", "claude-opus-5-5"), max_tokens=16000,
                                system=SVG_SYSTEM, output_config={"effort": "medium"},
                                messages=[{"role": "user", "content": prompt}]) as st:
        msg = st.get_final_message()
    txt = "".join(b.text for b in msg.content if b.type == "text")
    m = re.search(r"<svg[\s\S]*</svg>", txt)
    if not m: raise RuntimeError("SVG 가 오지 않았습니다 (stop_reason=%s)" % msg.stop_reason)
    svg = re.sub(r"<(text|script|foreignObject)[\s\S]*?</\1>", "", m.group(0))
    import xml.dom.minidom
    xml.dom.minidom.parseString(svg)                         # 壊れた SVG は保存しない (例外 → 作り直し)
    open(out + ".svg", "w", encoding="utf-8").write(svg); return out + ".svg"

def _save_raster(raw, out):
    """幅1024に縮めて保存 (リポジトリが重くならないように)"""
    from io import BytesIO
    from PIL import Image
    im = Image.open(BytesIO(raw)).convert("RGB")
    if im.size[0] > 1024: im = im.resize((1024, round(im.size[1] * 1024 / im.size[0])), Image.LANCZOS)
    im.save(out + ".png", optimize=True)

GEN = {"gemini": gen_gemini, "openai": gen_openai, "claude": gen_claude}

def ensure(s, force=False):
    """絵がなければ作る。作ったパス（作れなければ None）を返す"""
    if s.get("illust_off"): return None
    p = path_for(s)
    if p and not force: return p
    prov = provider()
    if prov not in GEN: return None
    out = os.path.join(DIR, key_for(s))
    order = [q for q in [prov] + [q for q in ("gemini", "openai", "claude") if q != prov and providers()[q]] if q not in DOWN]
    if not order: raise RuntimeError("쓸 수 있는 생성처가 없습니다 (" + ", ".join(sorted(DOWN)) + " 은 이번 작업에서 실패)")
    last = None
    for q in order:                                   # 第一候補がだめなら次の作り方で。429 が続く生成元は以後飛ばす
        try:
            p = GEN[q](prompt_for(s), out)
            json.dump({"provider": q, "prompt": describe(s)}, open(out + ".json", "w", encoding="utf-8"), ensure_ascii=False)
            return p
        except Exhausted as e:
            DOWN.add(q); last = e; print(f"    {q}: {e} → 이번 작업에서는 {q} 를 건너뜁니다", flush=True)
        except Exception as e:
            last = e; print(f"    {q} 실패: {str(e)[:160]}", flush=True)
    raise last

PHOTO_TEMPLATE = ("実写の写真のように見えるリアルな画像。{theme}。横長16:9。文字・ロゴ・透かしは一切入れない。"
                  "日本の風景・日本人の人物、自然光、報道写真や広告写真のような自然な構図。顔のアップは避ける。")

def ensure_photo(desc, force=False):
    """実写風の写真を生成（photo: "ai:説明"）。パスを返す。作れなければ None"""
    desc = desc.strip(); key = hashlib.md5(("photo", desc).__repr__().encode()).hexdigest()[:16]
    out = os.path.join(DIR, "photo_" + key)
    for ext in (".png", ".jpg", ".svg"):
        if os.path.exists(out + ext) and not force: return out + ext
    prov = provider()
    if prov not in GEN: return None
    order = [q for q in [prov] + [q for q in ("gemini", "openai") if q != prov and providers()[q]] if q not in DOWN and q != "claude"]
    last = None
    for q in order:
        try:
            p = GEN[q](PHOTO_TEMPLATE.format(theme=desc), out)
            json.dump({"provider": q, "prompt": desc, "kind": "photo"}, open(out + ".json", "w", encoding="utf-8"), ensure_ascii=False)
            return p
        except Exhausted as e:
            DOWN.add(q); last = e; print(f"    {q}: {e} → 이번 작업에서는 {q} 를 건너뜁니다", flush=True)
        except Exception as e:
            last = e; print(f"    {q} 실패: {str(e)[:160]}", flush=True)
    if last: raise last
    return None

def placement(s):
    """このスライドに絵が入るか（空きがあるか）を、白紙の絵で試して判定する: top / right / cover / none"""
    if s.get("illust_off") or s.get("illust_pos") == "none": return "none"
    if not os.path.exists(BLANK):
        from PIL import Image
        Image.new("RGB", (800, 450), "white").save(BLANK)
    import r8_goukaku as G
    return G.placement(s.get("title", ""), s.get("sub", ""), _ill_html(s, s.get("body", ""), BLANK))

def ensure_spec(spec, only=None, log=print):
    """spec の全スライドの絵をそろえる（すでにあるものは作らない）。作った枚数を返す"""
    if spec.get("illust_off"): return 0
    n = 0
    for i, s in enumerate(spec["slides"], 1):
        if only and i != only: continue
        if s.get("illust_off") or s.get("photo") or (path_for(s) and not only): continue
        if not only and placement(s) == "none":
            log(f"일러스트 {i:02d} – 공간이 없어 그림 없음  {s.get('title') or 'はじめに'}"); continue
        try:
            import time
            if n: time.sleep(PACE)                   # 続けて呼ぶと 429 になるので間を空ける
            p = ensure(s)
            if p: n += 1; log(f"일러스트 {i:02d} ✓ {os.path.basename(p)}  {s.get('title') or 'はじめに'}")
        except Exception as e:
            log(f"일러스트 {i:02d} ✗ {str(e)[:200]}")
    return n

def inject(s, body):
    """本文の先頭に絵を入れた HTML (絵がなければそのまま)"""
    p = path_for(s)
    if not p: return body
    return _ill_html(s, body, p)

BLANK = os.path.join(DIR, "_blank169.png")

def _ill_html(s, body, p):
    pos = s.get("illust_pos") or "auto"
    if pos == "none": return body
    if pos in ("auto", "top") and body.lstrip().startswith("<div class='cover'"): pos = "cover"
    return f"<div class='ill ill-{pos}'><img src='file://{p}'></div>" + body

def regen(path, i):
    """i枚目を別の絵に作り直す (seed を進めて spec に保存)"""
    sp = json.load(open(path, encoding="utf-8"))
    s = sp["slides"][i - 1]
    s.pop("illust_off", None)
    if path_for(s): s["illust_seed"] = int(s.get("illust_seed", 0)) + 1
    tmp = path + ".tmp"; json.dump(sp, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, path)
    return sp

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("spec", nargs="?"); ap.add_argument("--only", type=int); ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check or not a.spec:
        print("쓸 수 있는 방식:", providers(), "→ 사용:", provider()); sys.exit()
    path = a.spec
    sp = regen(path, a.only) if a.only else json.load(open(path, encoding="utf-8"))
    n = ensure_spec(sp, a.only)
    print(f"일러스트 {n}장 생성 ({provider()})")
