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

STYLE = ("Flat illustration in the style of Japanese free clip-art 'irasutoya': simple rounded shapes, soft pastel colors, "
         "thin dark-brown outlines, cute characters with round faces and small dot eyes, plain white background, "
         "lots of empty space around the subject, 4:3 composition. "
         "Absolutely no text, letters, numbers, signs or writing anywhere in the image.")
CAST = ("Main character (when a person is needed): a Japanese office worker in his late 20s with short black hair, "
        "white shirt and navy tie, studying for the real-estate license exam (宅建). "
        "Other people: simple clerks, examiners, customers as needed.")

def _key(name, env):
    if os.environ.get(env): return os.environ[env].strip()
    p = os.path.join(ROOT, name)
    return open(p).read().strip() if os.path.exists(p) else ""

def providers():
    return {"gemini": bool(_key(".gemini_api_key", "GEMINI_API_KEY")),
            "openai": bool(_key(".openai_api_key", "OPENAI_API_KEY")),
            "claude": bool(_key(".anthropic_api_key", "ANTHROPIC_API_KEY"))}

def provider():
    p = os.environ.get("ILLUST_PROVIDER")
    if p: return p
    av = providers()
    return next((k for k in ("gemini", "openai", "claude") if av[k]), "none")

def plain(htm):
    t = re.sub(r"<br\s*/?>|</(li|p|div|h\d|tr)>", "\n", htm or "")
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n\s*\n+", "\n", t).strip()

def describe(s):
    """スライドから絵の説明を作る（指定があればそれ）"""
    if s.get("illust"): return s["illust"].strip()
    txt = (s.get("title", "") + "\n" + plain(s.get("body", ""))).strip()
    return "このスライドの内容を表す場面:\n" + txt[:500]

def prompt_for(s):
    return (f"{STYLE}\n{CAST}\n\nDraw ONE simple scene that helps viewers understand the following slide of a Japanese "
            f"宅建 exam study video. Show the idea with 1-3 characters and a few simple objects (houses, documents, "
            f"calendars, money, checklists, etc.). Do not draw the slide text itself.\n\n{describe(s)}")

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

def _post(url, body, headers, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def gen_gemini(prompt, out):
    model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    parts = [{"text": prompt}]
    ref = os.path.join(DIR, "_ref.png")
    if os.path.exists(ref):
        parts.append({"text": "Use the same character design and drawing style as this reference image:"})
        parts.append({"inline_data": {"mime_type": "image/png", "data": base64.b64encode(open(ref, "rb").read()).decode()}})
    d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
              {"contents": [{"parts": parts}],
               "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "4:3"}}},
              {"x-goog-api-key": _key(".gemini_api_key", "GEMINI_API_KEY")})
    for c in d.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            data = (p.get("inlineData") or p.get("inline_data") or {}).get("data")
            if data:
                _save_raster(base64.b64decode(data), out); return out + ".png"
    raise RuntimeError("Gemini 가 이미지를 돌려주지 않았습니다: " + json.dumps(d, ensure_ascii=False)[:300])

def gen_openai(prompt, out):
    d = _post("https://api.openai.com/v1/images/generations",
              {"model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"), "prompt": prompt, "size": "1536x1024", "quality": "medium", "n": 1},
              {"Authorization": "Bearer " + _key(".openai_api_key", "OPENAI_API_KEY")})
    _save_raster(base64.b64decode(d["data"][0]["b64_json"]), out); return out + ".png"

SVG_SYSTEM = ("You draw illustrations as standalone SVG code. Style: Japanese free clip-art 'irasutoya' — flat pastel fills, "
              "thin dark-brown (#5a4636) outlines with round joins, cute characters with round heads and dot eyes, soft blush, "
              "simple props. Transparent background. viewBox='0 0 800 600'. Never draw any text, letters or numbers. "
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
    p = GEN[prov](prompt_for(s), out)
    json.dump({"provider": prov, "prompt": describe(s)}, open(out + ".json", "w", encoding="utf-8"), ensure_ascii=False)
    return p

def placement(s):
    """このスライドに絵が入るか（空きがあるか）を、白紙の絵で試して判定する: top / right / cover / none"""
    if s.get("illust_off") or s.get("illust_pos") == "none": return "none"
    if not os.path.exists(BLANK):
        from PIL import Image
        Image.new("RGB", (800, 600), "white").save(BLANK)
    import r8_goukaku as G
    return G.placement(s.get("title", ""), s.get("sub", ""), _ill_html(s, s.get("body", ""), BLANK))

def ensure_spec(spec, only=None, log=print):
    """spec の全スライドの絵をそろえる（すでにあるものは作らない）。作った枚数を返す"""
    if spec.get("illust_off"): return 0
    n = 0
    for i, s in enumerate(spec["slides"], 1):
        if only and i != only: continue
        if s.get("illust_off") or (path_for(s) and not only): continue
        if not only and placement(s) == "none":
            log(f"일러스트 {i:02d} – 공간이 없어 그림 없음  {s.get('title') or 'はじめに'}"); continue
        try:
            p = ensure(s)
            if p: n += 1; log(f"일러스트 {i:02d} ✓ {os.path.basename(p)}  {s.get('title') or 'はじめに'}")
        except Exception as e:
            log(f"illust {i:02d} ✗ {e}")
    return n

def inject(s, body):
    """本文の先頭に絵を入れた HTML (絵がなければそのまま)"""
    p = path_for(s)
    if not p: return body
    return _ill_html(s, body, p)

BLANK = os.path.join(DIR, "_blank.png")

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
