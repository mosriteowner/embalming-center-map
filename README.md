# embalming-center-map

一般社団法人 日本遺体衛生保全協会（IFSA）が公式サイトで公表している
「エンバーミングセンター案内」を都道府県別に集計し、センター数を色分け地図で示す静的ページを
**週1回自動更新**するリポジトリです。

- 出典: <https://www.embalming.jp/organization/>
- 公開ページ: `https://mosriteowner.github.io/embalming-center-map/`（Pages設定後）
- 非公式の集計であり、IFSA・各社とは無関係です。

## 仕組み

1. `src/update.py` が上記ページを取得（User-Agent明示・週1回・1リクエストのみ）
2. `src/parse.py` が県別の施設を抽出し、**ページ自身が記載する合計（○都道府県・事業会社○社・○センター）と一致するか検算**
   - 不一致なら何も更新せず失敗 → GitHub Actions の失敗通知が届く（誤った地図は公開されない）
3. 施設一覧が前回と変わっていれば `data/history.json` に日付つきで追記（増減が「変更履歴」に表示される）
4. `src/mapgen.py` が `docs/index.html`（色分けSVG地図・県別表・変更履歴）を生成
5. 変更があればActionsが自動コミット

色の区分は経年比較のため固定です（0 / 1 / 2 / 3 / 4〜5 / 6〜9 / 10〜19 / 20以上）。

## 初回セットアップ

1. GitHubで `embalming-center-map` リポジトリを作成し、このフォルダの中身をpush
2. **Actions** タブ → `update-map` → **Run workflow**（手動実行。実サイトでの取得・検算がここで初めて確認されます）
3. 成功したら **Settings → Pages** → Source: *Deploy from a branch* / Branch: `main` / Folder: `/docs`
4. 以降は毎週月曜朝に自動更新

初回の手動実行が失敗した場合は、ログの `[ERROR]` を確認してください
（ページの書式が想定と違うと、検算で止まるように作ってあります）。

## ローカルでの確認

```bash
pip install -r requirements.txt pytest
python -m pytest -q tests
python src/update.py          # docs/index.html が生成されます
```

## 既知の制約

- 掲載がない県は「0件（灰色）」で表示しますが、これは**IFSAの公表ページに掲載がない**という意味で、
  その県で実施できないという意味ではありません。
- 小笠原諸島・奄美群島は地図上で省略し、沖縄県は位置を移して枠内に表示しています。
- 地図データは `data/japan_simplified.geojson`（簡略化済み）です。元データは
  <https://github.com/dataofjapan/land> の `japan.geojson` を `tools/prepare_geo.py` で軽量化したものです。
  **公開前に、元データの利用条件を必ず確認してください。** 問題がある場合は国土数値情報などの
  出典明示で使える公的データに差し替えてください（`tools/prepare_geo.py` の入力を変えるだけです）。
- `tests/test_parse.py` の fixture は実サイトの構造を模した合成HTMLです。

## ライセンス

コード: お好みのライセンスを設定してください（未設定の場合は著作権者が権利を留保します）。
IFSAページの内容そのものはIFSAに帰属します。本リポジトリは施設数の集計結果のみを扱います。
