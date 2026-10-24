# coaching/yt — YouTube 動画パイプライン (令和8年度 宅建 解答解説)

HTML → PNG → Google Cloud TTS → ffmpeg で、ナレーション同期のスクロール動画を作る。

## 準備
```
python3 -m pip install weasyprint pdfplumber pillow
apt-get install -y fonts-noto-cjk ffmpeg poppler-utils
export GOOGLE_TTS_API_KEY=...      # Google Cloud Text-to-Speech の API キー
```

## 使い方
```
cd coaching/yt
python3 r8_subject.py --subject kenri        # 科目別ロング (kenri / horei / zei / gyoho)。27MB 超は part1, part2 に自動分割
python3 r8_subject.py --subject kenri --only 3   # 1問だけ (確認用)
python3 r8_subject.py --shorts [--only 3]    # ショート 50本 (1080x1920)
python3 r8_goukaku.py [--only 5]             # スライド＋ナレーション型 (合格点予想まとめ)
```
出力は `out/` (git 管理外)。`YT_OUT=/path` で変更可。

## 品質オプション (環境変数)
| 変数 | 既定 | 内容 |
|---|---|---|
| `YT_HIGHLIGHT` | `1` | 問題動画: 読んでいる肢の行を黄色でハイライト。スライド動画: 画面下に「いま読んでいる文」の字幕帯 |
| `YT_BGM` | (自動) | BGM ファイル。未指定なら `bgm/` の先頭ファイル。何も無ければ仮のパッド音 |
| `YT_PART_MB` | `27` | ロング動画の分割サイズ (MB)。`0` で分割せず1本にする |
| `YT_BGM_DB` | `-22` | BGM の音量 (dB)。`0` 以上で BGM なし。ナレーション中は自動で音量が下がる (ダッキング) |

BGM は YouTube オーディオライブラリ等から mp3 を `bgm/` に入れるだけ (git 管理外)。ファイル名が `_` で始まるものは無視。

## ファイル
- `vkit.py` — 共通: TTS (SSML mark で時刻取得、宅建→たっけん 等の読み固定)、描画、スクロール、ハイライト状態切替、字幕帯、BGM ミックス、分割
- `r8_q.py` / `r8_exp.py` — 令和8年度 全50問の問題文・独自解答・全肢の解説
- `r8_subject.py` — 科目別ロング & ショート
- `r8_goukaku.py` — スライド型の例 (合格点予想まとめ)。`slide(title, body_html, speech)` を並べれば別テーマでも使える

※ 解答は独自解答。公式正答が出たら r8_q.py / r8_exp.py を直して該当問題を `--only N` で作り直す。
