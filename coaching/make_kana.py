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
import make_audio_eleven  # noqa: E402
from make_audio_eleven import chapter_text  # noqa: E402

make_audio_eleven.READINGS.clear()  # ひらがな置換はここ (FIX) で品詞つきで行う

DIC = os.environ.get("UNIDIC_DIR", "/tmp/claude-0/dl/unidic-lite-1.0.8/unidic_lite/dicdir")
KANJI = re.compile(r"[一-鿿々〆ヶ]")

# 形態素解析の誤り/連濁・促音の補正 (表層 → 読み)。make_audio_eleven.READINGS より後に適用。
# 値は 読み、または (読み, 品詞)。品詞は文節の切れ目判定に使う (既定は 名詞)。
FIX = {
    "主として": ("しゅとして", "副詞"),
    "何を": ("なにを", "助詞"),
    "何が": ("なにが", "助詞"),
    "何で": ("なにで", "助詞"),
    "一戸建て街": "いっこだてがい",
    "一戸建て": "いっこだて",
    "線引き": "せんびき",
    "建蔽率": "けんぺいりつ",
    "遅滞なく": ("ちたいなく", "副詞"),
    "5t超": "5トンちょう",
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


GLUE_POS = {"助詞", "助動詞", "接尾辞", "補助記号", "記号", "空白"}
GLUE_WORDS = {"ない", "なく", "なし", "する", "し", "した", "して", "できる", "でき", "される", "され", "すべき", "等", "とう"}


def to_kana(text, tg):
    """漢字→ひらがな。さらに文節の切れ目にだけ半角スペースを入れる (合成語の中では切らない)。
    ひらがなだけの長い文字列だと TTS が単語の境界を誤って変な所で切るため。"""
    def tokens():
        pat = re.compile("(" + "|".join(map(re.escape, sorted(FIX, key=len, reverse=True))) + ")")
        for seg in pat.split(text):
            if not seg:
                continue
            if seg in FIX:
                v = FIX[seg]
                rd, pos = (v, "名詞") if isinstance(v, str) else v
                yield seg, pos, rd
                continue
            for w in tg(seg):
                s, f = w.surface, w.feature
                pos = f[0] if f else ""
                if KANJI.search(s):
                    kana = f[17] if len(f) > 17 and f[17] not in ("*", "") else (f[9] if len(f) > 9 and f[9] != "*" else "")
                    yield s, pos, (kata2hira(kana) if kana else s)
                else:
                    yield s, pos, s

    out, prev = [], None
    for s, pos, rd in tokens():
        glue = (prev is None or pos in GLUE_POS or s in GLUE_WORDS
                or prev[0] in ("接頭辞", "補助記号", "記号", "空白")
                or (prev[0] == "名詞" and pos == "名詞")
                or (prev[0] in ("動詞", "形容詞") and pos in ("動詞", "形容詞")))
        if not glue:
            out.append(" ")
        out.append(rd)
        prev = (pos, s)
    return "".join(out).replace(" 、", "、").replace(" 。", "。").replace("、 ", "、").replace("。 ", "。")


def convert(text, tg):
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
