# -*- coding: utf-8 -*-
"""学習サイト (:8788) の資料を takken.ekunblog.com の記事にする（YouTube からの受け皿。SEO より「見やすさ」優先）。
  python3 coaching/blog/study_posts.py --list           … 記事の一覧と発行状況
  python3 coaching/blog/study_posts.py --dry            … HTML を coaching/blog/study/ に書き出すだけ
  python3 coaching/blog/study_posts.py                  … 全部発行（同じスラッグがあれば更新）
  python3 coaching/blog/study_posts.py --only takken-toshi-anki
載せるもの: 令和8年度 本試験の解答解説（4分野）、都市計画法・建築基準法の暗記ノート（音声つき）、建築基準法 一問一答100
載せないもの: 間違えた回数・理由などの個人の記録（誤答ノート・統計）
"""
import argparse, html, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "coaching")); sys.path.insert(0, os.path.join(ROOT, "coaching", "yt"))
SITE = "https://takken.ekunblog.com"
STATE = os.path.join(HERE, "study_posts.json")
OUTD = os.path.join(HERE, "study")
AUDIO = os.path.join(ROOT, "static", "audio")
DOCS = os.path.join(ROOT, "static", "docs")
CHANNEL = "https://www.youtube.com/@nippon-real"
E = html.escape

# ---------------- 記事の定義 ----------------
R8 = [("kenri", "権利関係", "問1〜問14", list(range(1, 15)), "R8_kenri"),
      ("horei", "法令上の制限", "問15〜問22", list(range(15, 23)), "R8_horei"),
      ("zei", "税・その他（5問免除科目を含む）", "問23〜25・問46〜50", [23, 24, 25, 46, 47, 48, 49, 50], "R8_zei"),
      ("gyoho", "宅建業法", "問26〜問45", list(range(26, 46)), "R8_gyoho")]

def posts():
    out = []
    for key, name, rng, nums, vkey in R8:
        out.append({"slug": f"takken-r8-{key}", "kind": "r8", "nums": nums, "video": vkey, "thumb": ["令和8年度 宅建", name.split("（")[0], rng + " 解説"],
                    "title": f"【令和8年度 宅建】{name} {rng} 解答解説（全選択肢の○×と理由）",
                    "excerpt": f"令和8年度（2026年10月18日実施）宅建士試験の{name}（{rng}）を1問ずつ解説。正解と、4つの選択肢すべての○×の理由をまとめています。"})
    out.append({"slug": "takken-toshi-anki", "kind": "anki", "subj": "toshi",
                "title": "【宅建 法令上の制限】都市計画法 暗記ノート（全13章・聞き流し音声つき）", "thumb": ["都市計画法", "暗記ノート", "全13章・音声つき"],
                "excerpt": "宅建の問15・16（都市計画法）で問われるポイントを13章にまとめた暗記ノート。章ごとの聞き流し音声とPDFつき。"})
    out.append({"slug": "takken-kenki-anki", "kind": "anki", "subj": "kenki",
                "title": "【宅建 法令上の制限】建築基準法 暗記ノート（全12章・聞き流し音声つき）", "thumb": ["建築基準法", "暗記ノート", "全12章・音声つき"],
                "excerpt": "宅建の問17・18（建築基準法）で問われるポイントを12章にまとめた暗記ノート。章ごとの聞き流し音声とPDFつき。"})
    out.append({"slug": "takken-kenki-100", "kind": "q100", "subj": "kenki",
                "title": "【宅建】建築基準法 一問一答100問（答え・解説つき）", "thumb": ["建築基準法", "一問一答", "100問"],
                "excerpt": "宅建の建築基準法（問17・18）対策の4択100問。タップすると正解と解説が開きます。"})
    return out

def state():
    return json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}

def url_of(slug):
    return (state().get(slug) or {}).get("url") or f"{SITE}/{slug}/"

# ---------------- 部品 ----------------
def P(text): return f"<!-- wp:paragraph -->\n<p>{text}</p>\n<!-- /wp:paragraph -->"
def H2(text): return f"<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">{E(text)}</h2>\n<!-- /wp:heading -->"
def RAW(h): return f"<!-- wp:html -->\n{h}\n<!-- /wp:html -->"
BOX = "border:1px solid #d9dee8;border-radius:10px;padding:14px 16px;margin:14px 0;background:#fff;"
KEY = "background:#fff3c4;border-left:6px solid #e0a800;padding:10px 14px;margin:10px 0;font-weight:bold;"
OK, NG = "color:#1f7a45;font-weight:bold;", "color:#c0392b;font-weight:bold;"

def red(s):
    """暗記ノートの {{重要語}} を赤字に"""
    return re.sub(r"\{\{(.+?)\}\}", r"<strong style='color:#c0392b'>\1</strong>", E(s))

def toc(items):
    if all(len(t) <= 5 for _a, t in items):          # 「問1」のような短い目次は横に並べる
        return RAW("<div style='" + BOX + "background:#f7f9fc'><b>目次</b><div style='display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:6px'>" +
                   "".join(f"<a href='#{a}'>{E(t)}</a>" for a, t in items) + "</div></div>")
    return RAW("<div style='" + BOX + "background:#f7f9fc'><b>目次</b><ol style='margin:6px 0 0 1.2em'>" +
               "".join(f"<li><a href='#{a}'>{E(t)}</a></li>" for a, t in items) + "</ol></div>")

def footer(slug):
    others = [p for p in posts() if p["slug"] != slug]
    li = "".join(f"<li><a href='{url_of(p['slug'])}'>{E(p['title'])}</a></li>" for p in others)
    return [H2("あわせて読みたい"), RAW(f"<ul>{li}</ul>"),
            P(f"宅建の解説動画は YouTube チャンネル <a href=\"{CHANNEL}\" target=\"_blank\" rel=\"noopener\">NIPPONリアル</a> で公開しています。")]

# ---------------- 令和8年度 解答解説 ----------------
def r8_html(p):
    import r8_q, r8_exp
    Q = {q["n"]: q for q in r8_q.Q}
    parts = [P(E(p["excerpt"])),
             P("問題を読んで自分で答えを決めてから、「正解と解説を見る」を開いてください。正解は当チャンネルの独自解答です。"
               "公式の正解は11月25日（合格発表日）に不動産適正取引推進機構から発表されます。"),
             P("動画でも解説しています。"), "<!--YOUTUBE_EMBED-->",
             toc([(f"q{n}", f"問{n}") for n in p["nums"]])]
    for n in p["nums"]:
        q = Q[n]; ex = r8_exp.EXP.get(n, [])
        b = f"<div id='q{n}' style='{BOX}'><p style='font-weight:bold;color:#1a3d7c;margin:0 0 6px'>問{n}</p><p>{E(q['stem'])}</p>"
        for s in q["subs"]: b += f"<p style='margin:4px 0 4px 1em'>{E(s)}</p>"
        b += "<ol style='margin:8px 0 0 1.4em'>" + "".join(f"<li style='margin:4px 0'>{E(c)}</li>" for c in q["choices"]) + "</ol>"
        rows = "".join(f"<tr><td style='white-space:nowrap;padding:6px 8px;border-top:1px solid #eee'>{E(lab)}</td>"
                       f"<td style='padding:6px 8px;border-top:1px solid #eee;{OK if mk == '○' else NG}'>{E(mk)}</td>"
                       f"<td style='padding:6px 8px;border-top:1px solid #eee'>{E(why)}</td></tr>" for lab, mk, why in ex)
        b += (f"<details style='margin-top:10px'><summary style='cursor:pointer;color:#1a3d7c;font-weight:bold'>正解と解説を見る</summary>"
              f"<div style='{KEY}'>正解：{q['answer']}</div>"
              + (f"<table style='width:100%;border-collapse:collapse;font-size:0.95em'>{rows}</table>" if rows else f"<p>{E(q.get('exp', ''))}</p>")
              + "</details></div>")
        parts.append(RAW(b))
    parts.append("<!--YOUTUBE_LINK-->")
    return parts

# ---------------- 暗記ノート ----------------
def anki_html(p, media):
    import subjects
    key = p["subj"]; name = subjects.name(key); ch = subjects.chapters(key)
    tracks = {t["n"]: t for t in json.load(open(os.path.join(AUDIO, f"{key}_tracks.json"), encoding="utf-8"))["tracks"]} if os.path.exists(os.path.join(AUDIO, f"{key}_tracks.json")) else {}
    parts = [P(E(p["excerpt"])),
             P("赤字が試験で問われるところです。音声は章ごとに聞けるので、通勤中や寝る前の聞き流しにどうぞ。")]
    allp = os.path.join(AUDIO, f"{key}_all.mp3")
    u = media(allp)
    if u: parts.append(RAW(f"<div style='{BOX}'><b>全章通しの音声</b><audio controls preload='none' src='{u}' style='width:100%;margin-top:6px'></audio></div>"))
    pdfs = [(f"{key}_note.pdf", f"{name} 暗記ノート（PDF）"), (f"{key}_100.pdf", f"{name} 一問一答100（PDF）"), (f"{key}_test.pdf", f"{name} 確認テスト（PDF）")]
    links = [(media(os.path.join(DOCS, f)), lab) for f, lab in pdfs]
    links = [(u, lab) for u, lab in links if u]
    if links: parts.append(RAW("<ul>" + "".join(f"<li><a href='{u}' target='_blank'>{E(lab)}</a></li>" for u, lab in links) + "</ul>"))
    parts.append(toc([(f"c{i}", c["title"]) for i, c in enumerate(ch, 1)]))
    for i, c in enumerate(ch, 1):
        parts.append(f"<!-- wp:heading -->\n<h2 class=\"wp-block-heading\" id=\"c{i}\">{E(c['title'])}</h2>\n<!-- /wp:heading -->")
        b = f"<p style='color:#555'>{E(c['meaning'])}</p>"
        t = tracks.get(i)
        if t:
            u = media(os.path.join(AUDIO, t["file"]))
            if u: b += f"<audio controls preload='none' src='{u}' style='width:100%'></audio>"
        b += "<ul style='margin:10px 0 0 1.2em'>" + "".join(f"<li style='margin:6px 0'>{red(it)}</li>" for it in c["items"]) + "</ul>"
        b += f"<div style='{KEY}'>ひとことで：{E(c['one'])}</div>"
        parts.append(RAW(f"<div style='{BOX}'>{b}</div>"))
    return parts

# ---------------- 一問一答100 ----------------
def q100_html(p):
    qs = json.load(open(os.path.join(ROOT, "coaching", f"{p['subj']}_100.json"), encoding="utf-8"))
    tags = []
    for q in qs:
        if q.get("tag") not in tags: tags.append(q.get("tag"))
    parts = [P(E(p["excerpt"])), P("分野ごとに並んでいます。まず自分で答えを決めてから開いてください。")]
    parts.append(toc([(f"t{i}", t or "その他") for i, t in enumerate(tags, 1)]))
    for i, t in enumerate(tags, 1):
        parts.append(f"<!-- wp:heading -->\n<h2 class=\"wp-block-heading\" id=\"t{i}\">{E(t or 'その他')}</h2>\n<!-- /wp:heading -->")
        for q in [x for x in qs if x.get("tag") == t]:
            b = f"<div style='{BOX}'><p style='font-weight:bold;color:#1a3d7c;margin:0 0 6px'>第{q['n']}問</p><p>{E(q['stem'])}</p>"
            for s in q.get("subs") or []: b += f"<p style='margin:4px 0 4px 1em'>{E(s)}</p>"
            b += "<ol style='margin:8px 0 0 1.4em'>" + "".join(f"<li style='margin:4px 0'>{E(c)}</li>" for c in q["choices"]) + "</ol>"
            b += (f"<details style='margin-top:8px'><summary style='cursor:pointer;color:#1a3d7c;font-weight:bold'>正解と解説</summary>"
                  f"<div style='{KEY}'>正解：{q['answer']}</div><p>{E(q.get('exp', ''))}</p></details></div>")
            parts.append(RAW(b))
    return parts

# ---------------- 組み立て・発行 ----------------
def build(p, media=lambda path: None):
    body = {"r8": r8_html, "q100": q100_html}.get(p["kind"])
    parts = body(p) if body else anki_html(p, media)
    return "\n\n".join(parts + footer(p["slug"])) + "\n"

def youtube(p):
    if not p.get("video"): return ""
    import registry
    return (registry.get(registry.load(), p["video"]) or {}).get("url", "")

# 動画の概要欄に足すブログへの誘導（動画の台帳 key → この記事たち）
VIDEO_LINKS = {"R8_kenri": ["takken-r8-kenri"], "R8_zei": ["takken-r8-zei"], "R8_gyoho": ["takken-r8-gyoho"],
               "R8_horei": ["takken-r8-horei", "takken-toshi-anki", "takken-kenki-anki", "takken-kenki-100"],
               "R8_full": ["takken-r8-kenri", "takken-r8-horei", "takken-r8-zei", "takken-r8-gyoho"]}
LINK_LABEL = {"takken-r8-kenri": "権利関係 問1〜14 の問題と全選択肢の解説", "takken-r8-horei": "法令上の制限 問15〜22 の問題と全選択肢の解説",
              "takken-r8-zei": "税・その他 問23〜25・46〜50 の問題と全選択肢の解説", "takken-r8-gyoho": "宅建業法 問26〜45 の問題と全選択肢の解説",
              "takken-toshi-anki": "都市計画法 暗記ノート（音声つき）", "takken-kenki-anki": "建築基準法 暗記ノート（音声つき）", "takken-kenki-100": "建築基準法 一問一答100問"}

def yt_lines():
    """{動画 key: 概要欄に貼る文}"""
    out = {}
    for vkey, slugs in VIDEO_LINKS.items():
        out[vkey] = "▼ブログで読む（文字で復習）\n" + "\n".join(f"・{LINK_LABEL[s]}\n{url_of(s)}" for s in slugs)
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--list", action="store_true"); ap.add_argument("--dry", action="store_true"); ap.add_argument("--only"); ap.add_argument("--yt", action="store_true")
    a = ap.parse_args()
    if a.yt:
        import registry
        reg = registry.load()
        for k, t in yt_lines().items():
            v = registry.get(reg, k) or {}
            print(f"===== {v.get('label') or k}  {v.get('url', '')}\n{t}\n")
        return
    st = state()
    todo = [p for p in posts() if not a.only or p["slug"] == a.only]
    if a.list:
        for p in posts(): print(f"{'✓' if p['slug'] in st else '・'} {p['slug']:22s} {p['title']}  {(st.get(p['slug']) or {}).get('url', '')}")
        return
    if a.dry:
        os.makedirs(OUTD, exist_ok=True)
        for p in todo:
            fn = os.path.join(OUTD, p["slug"] + ".html"); open(fn, "w", encoding="utf-8").write(build(p)); print("저장:", fn)
        return
    import publish_wp
    au = publish_wp.auth(); cache = {}
    def media(path):
        if not os.path.exists(path): return None
        if path not in cache:
            try: cache[path] = publish_wp.upload_media(path, au=au); print(f"  ↑ 업로드 {os.path.basename(path)}", flush=True)
            except Exception as e: cache[path] = None; print(f"  ✗ {os.path.basename(path)} 업로드 실패: {e}", flush=True)
        return cache[path]
    for p in todo:
        print(f"… {p['title']}", flush=True)
        content = build(p, media)
        yt = youtube(p)
        fid = publish_wp.featured_image(yt, p.get("thumb"), p["slug"], au=au)
        link, action, status, slug = publish_wp.publish(content, p["title"], p["slug"], p["excerpt"], yt, au=au, featured=fid)
        st[p["slug"]] = {"url": link, "title": p["title"], "at": time.strftime("%Y-%m-%d %H:%M"), "youtube": yt}
        json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"✓ {action} ({status}): {link}" + ("" if yt or not p.get("video") else "  ※ 영상 URL 미등록이라 임베드 없음 (URL 대장에 넣고 다시 발행)"), flush=True)
    print("완료.")

if __name__ == "__main__":
    main()
