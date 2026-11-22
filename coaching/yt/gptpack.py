# -*- coding: utf-8 -*-
"""ChatGPT に 1 回貼るだけで「本編サムネイル(16:9)・ショートサムネイル(9:16)・タイトル・概要欄」が出るようにまとめた文章を作る。
  スタジオの「📋 ChatGPT용 한 번에 복사」ボタン（/studio/api/gptpack/<name>）と、python3 gptpack.py specs/XXX.json から使う。
  ・本編: thumb.prompt_for（docs/THUMB_STYLE.md の形）＋ ytext.compose のタイトル・概要欄
  ・ショート: この本編を short_target にしている専用台本（SHORT_*）と、本編から切り出したショート（out/<outdir>/shorts/*.txt）
  サムネイルは自動では作らない（docs/SHORTS_RULES.md §4）。ChatGPT に貼るのは人が行う。
"""
import glob, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
SPECS = os.path.join(HERE, "specs")

def _short_items(spec, reg=None):
    """[{label, title, desc, pin, prompt}] — ショート専用 spec そのもの、または本編に紐づくショート"""
    import registry, shorts
    reg = reg or registry.load(); out = []
    def from_spec(sp):
        s = sp["slides"][0]
        hook = s.get("short_hook") or (s.get("title") or sp.get("label", "")).replace("｜", "\n")
        desc = (s.get("short_desc") or shorts.desc_line(s.get("speech") or "") or hook.replace("\n", " "))[:70]
        v = registry.get(reg, sp.get("short_target") or sp["name"]) or {}
        url = v.get("url") or ""
        return {"label": (sp.get("label") or sp["name"]).replace("【ショート】", ""),
                "title": f"{hook.replace(chr(10), '｜')} {sp.get('short_tags') or '#宅建 #宅建士'}", "desc": desc,
                "pin": f"詳しくは本編で▶ {url}" if url else "（本編の URL を登録すると、ここに固定コメント用の一文が入ります）",
                "prompt": shorts.thumb_prompt(sp, s, hook, desc)}
    if spec.get("short_target"): return [from_spec(spec)]
    for p in sorted(glob.glob(os.path.join(SPECS, "*.json"))):                       # この本編のショート専用台本
        try: sp = json.load(open(p, encoding="utf-8"))
        except Exception: continue
        if sp.get("short_target") == spec["name"] and sp.get("slides"): out.append(from_spec(sp))

    outdir = os.path.join(os.environ.get("YT_OUT", os.path.join(HERE, "out")), spec.get("outdir") or spec["name"].lower(), "shorts")
    for t in sorted(glob.glob(os.path.join(outdir, "*.txt"))):                       # 本編から切り出したショート
        txt = open(t, encoding="utf-8").read()
        g = lambda k: (re.search(rf"【{k}】\n(.*?)(?=\n\n【|\Z)", txt, re.S) or [None, ""])[1].strip()
        if g("タイトル"): out.append({"label": os.path.basename(t)[:-4], "title": g("タイトル"), "desc": g("概要欄"), "pin": g("固定コメント"),
                                       "prompt": g("ChatGPT サムネイル用プロンプト（9:16）")})
    return out

def pack(spec):
    """ChatGPT に貼る全文と、画面に出す内訳を返す"""
    import thumb, ytext
    is_short = bool(spec.get("short_target"))
    try: shorts_ = _short_items(spec)
    except Exception as e: shorts_ = []; err = str(e)[:120]
    else: err = ""
    n_img = (0 if is_short else 1) + len([x for x in shorts_ if x.get("prompt")])
    L = ["次の指示どおりに作業してください。途中で質問はしないでください。",
         "このチャットの過去のやり取りや、ほかの動画の内容・文字は一切使わないでください（下に書いてある文字だけを使う）。", "",
         f"■ 画像は全部で {n_img} 枚。1回の返信で作るのは1枚だけです。",
         "・この返信では【画像1】だけを生成し、そのあと「作業2」の文章を出力する。"]
    if n_img > 1: L += ["・そのあと私が「次」と送るたびに、【画像2】【画像3】…を順番に1枚ずつ生成する。そのときは、その画像の指定だけを使い、ほかの画像の文字や内容を混ぜない。"]
    L += ["", "■ 作業1：画像の指定", ""]
    k = 0; yt = None
    if not is_short:
        cfg = dict(spec.get("thumb") or {}) or thumb.suggest(spec)
        k += 1
        L += [f"━━【画像{k}】本編（ロング動画）用サムネイル｜横長 16:9 ━━", thumb.prompt_for(spec, cfg, True, False)]
        if cfg.get("scene"): L += [f"【人物・場面の指定（上の背景の説明より優先）】\n{cfg['scene']}"]     # 例: 作業着で圧着工具を持つ20代の男性
        L += [""]
        yt = ytext.compose(spec)
    for x in shorts_:
        if not x.get("prompt"): continue
        k += 1
        L += [f"━━【画像{k}】ショート用サムネイル｜縦長 9:16｜{x['label']} ━━", x["prompt"], ""]
    L += ["■ 作業2：【画像1】を出した同じ返信の中で、下の【】ごとの文章を、それぞれ別のコードブロックで出力する。",
          "一字一句そのまま出力し、言い換え・要約・翻訳・追記はしない（コピーして YouTube に貼るため）。見出しは日本語のまま付ける。", ""]
    if yt:
        L += ["【本編 タイトル】", yt["title"], "", "【本編 概要欄】", yt["description"], ""]
        if yt.get("tags"): L += ["【本編 タグ】", yt["tags"], ""]
    for j, x in enumerate(shorts_, 1):
        tag = f"ショート{j if len(shorts_) > 1 else ''}"
        L += [f"【{tag} タイトル】", x["title"], "", f"【{tag} 概要欄】", x["desc"], "", f"【{tag} 固定コメント】", x["pin"], ""]
    text = "\n".join(L).strip() + "\n"
    return {"text": text, "images": n_img, "shorts": len(shorts_), "chars": len(text), "warn": ([f"쇼츠 목록을 읽지 못했습니다: {err}"] if err else []) + ((yt or {}).get("warn") or [])}

if __name__ == "__main__":
    r = pack(json.load(open(sys.argv[1], encoding="utf-8")))
    print(r["text"]); print(f"--- 画像 {r['images']} 枚・ショート {r['shorts']} 本・{r['chars']} 字", file=sys.stderr)
