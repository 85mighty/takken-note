# -*- coding: utf-8 -*-
"""暗記ノートの読み上げ文を、漢字→ひらがなに展開した「読み確定版」台本 (toshi_kana.json) にする。
開発環境でのみ実行 (fugashi + unidic-lite の辞書が必要)。結果は git にコミットし、VPS 側はそれを読むだけ。
  python3 coaching/make_kana.py            # coaching/toshi_kana.json を更新
  python3 coaching/make_kana.py --show 3   # 第3章の変換結果を表示
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import toshi_gen  # noqa: E402
from make_audio_eleven import chapter_text, READINGS  # noqa: E402

DIC = os.environ.get("UNIDIC_DIR", "/tmp/claude-0/dl/unidic-lite-1.0.8/unidic_lite/dicdir")
KANJI = re.compile(r"[一-鿿々〆ヶ]")

# 形態素解析の誤り/連濁・促音の補正 (表層 → 読み)。make_audio_eleven.READINGS より後に適用。
FIX = {
    "主として": "しゅとして",
    "何を": "なにを",
    "何が": "なにが",
    "何で": "なにで",
    "一戸建て": "いっこだて",
    "建基法": "けんきほう",
    "30日前": "30にちまえ",
    "5t": "5トン",
    "第一種": "だいいっしゅ",
    "第二種": "だいにしゅ",
    "一低": "いちてい",
    "二低": "にてい",
    "一住": "いちじゅう",
    "二住": "にじゅう",
    "準住": "じゅんじゅう",
    "近商": "きんしょう",
    "準工": "じゅんこう",
    "工専": "こうせん",
    "準都計": "じゅんとけい",
    "伝建": "でんけん",
    "都府県": "とふけん",
    "県境": "けんざかい",
}


def kata2hira(s):
    return "".join(chr(ord(ch) - 0x60) if "ァ" <= ch <= "ヶ" else ch for ch in s)


def tagger():
    from fugashi import GenericTagger
    return GenericTagger(f"-d {DIC} -r {DIC}/mecabrc" if os.path.exists(DIC + "/mecabrc") else f"-d {DIC}")


def to_kana(text, tg):
    out = []
    for w in tg(text):
        s = w.surface
        if not KANJI.search(s):
            out.append(s)
            continue
        f = w.feature
        kana = f[17] if len(f) > 17 and f[17] not in ("*", "") else (f[9] if len(f) > 9 and f[9] != "*" else "")
        out.append(kata2hira(kana) if kana else s)
    return "".join(out)


def convert(text, tg):
    for k, v in FIX.items():
        text = text.replace(k, v)
    return to_kana(text, tg)


def main():
    tg = tagger()
    res = {}
    for i, c in enumerate(toshi_gen.CHAPTERS, 1):
        res[str(i)] = convert(chapter_text(c), tg)
    if len(sys.argv) > 2 and sys.argv[1] == "--show":
        print(res[sys.argv[2]])
        return
    with open(os.path.join(HERE, "toshi_kana.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    left = sum(len(KANJI.findall(t)) for t in res.values())
    print("書き出し: toshi_kana.json / 残った漢字:", left, "/ 合計", sum(map(len, res.values())), "文字")


if __name__ == "__main__":
    main()
