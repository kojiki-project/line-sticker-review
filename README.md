# LINE Sticker Review Catalog

完成済みの動くLINEスタンプを、スマホで検索・再生・透過確認・保存できる静的レビューカタログです。プレーンHTML/CSS/JavaScriptのみで動き、CDN・npm・ビルド工程はありません。

## 現在の収録商品

- **動く！すきが多めのもふ恋** — APNG 16点
- 制作元の記録上、機械QA・Chromium実再生QA・動画QA・梱包QAはPASS
- **未実施:** LINE Creators Marketへの申請・審査・販売、価格決定、販売者アカウント情報の入力

## ローカルで見る

`file://` ではJSON取得がブラウザに拒否されるため、必ず静的サーバーで開きます。

```bash
cd line-sticker-review
python3 -m http.server 4173 --bind 127.0.0.1
```

ブラウザで `http://127.0.0.1:4173/` を開いてください。

## 検証

```bash
cd line-sticker-review
python3 scripts/verify_catalog.py
```

検証内容は、商品数1、スタンプ数16、必須ファイル、全APNGの `acTL` チャンク、宣言寸法、ラベル欠落、内部相対URL、LINE用ZIP、完全版ZIPがリポジトリ内にないことです。

商品追加後は件数を明示します。

```bash
python3 scripts/verify_catalog.py --expected-products 2 --expected-items 16
```

`--expected-items` は各商品に同じ点数を期待する現在の検証方式です。点数が異なる商品を混在させる場合は、商品別の期待値を検証スクリプトへ追加してください。

## データ構造

```text
data/products/index.json             # 商品一覧・商品データへの参照
data/products/<slug>.json            # 商品情報・QA・全スタンプのメタデータ
assets/products/<slug>/stickers/     # 配信用APNG
assets/products/<slug>/stills/       # START/END静止フレーム
assets/products/<slug>/review/       # 動画・確認シート
assets/products/<slug>/qa/           # 制作元のQA記録
assets/products/<slug>/downloads/    # LINEアップロード用ZIPだけ
assets/fonts/                        # ローカル日本語フォントとライセンス
```

`app.js` は `data/products/index.json` を読み、商品データから画面を生成します。2商品以上になるとヘッダーの商品切替が自動表示されます。

## 新しいパックを追加する（正確な手順）

### 1. 完成素材を同じ規約で用意

ビルダーは素材ルートに次のファイルを要求します。

- `docs/manifest.json`
- `release/line/main.png`, `tab.png`, およびmanifest記載IDの `<ID>.png`
- `build/frames/<ID>/00.png` と `15.png`
- `review/contact_sheet.png`, `start_end.png`, `character_sheet.png`, `preview.mp4`
- `qa/all_machine.json`, `all_browser.json`, `video.json`, `package.json`
- `assets/masters/characters.json`
- `assets/fonts/ReviewSans.otf`, `assets/fonts/LICENSE.txt`
- `qa/package.json` が示すLINEアップロード用ZIP

`manifest.json` の `count` と `stickers` 配列数は一致させ、各スタンプに `id`, `character`, `text`, `motion`, `start`, `end`, `use`, `frames`, `frame_ms`, `loops` を入れます。キャラクターIDは現在 `dog`, `cat`, `bunny`, `trio` に対応しています。

### 2. ビルダーを実行

以下の4値だけを新商品用に置き換えます。

```bash
cd line-sticker-review
python3 scripts/build_product.py \
  /absolute/path/to/finished-pack \
  --slug url-safe-product-slug \
  --complete-url https://github.com/OWNER/REPO/releases/download/TAG/complete_delivery.zip
```

- `--slug` は英小文字・数字・ハイフンで重複しない値にします。
- 同じslugを再実行すると商品データとコピー済み素材を更新します。
- 完全版ZIP本体はコピーしません。外部Release URLだけをJSONへ記録します。
- LINEアップロード用ZIPは `assets/products/<slug>/downloads/` にコピーします。

### 3. 生成結果を検証

```bash
python3 scripts/verify_catalog.py \
  --expected-products <data/products/index.jsonの商品数> \
  --expected-items <その商品のスタンプ数>
```

続けて静的サーバーを起動し、検索、キャラクター絞り込み、背景切替、全再生、カード詳細、START→END、各保存リンク、動画を実ブラウザで確認します。390px幅で横スクロールがないことも確認してください。

## ダウンロードの扱い

- LINEアップロード用ZIPはこのカタログに同梱しています。
- 完全版デリバリーZIPは大容量のため同梱せず、GitHub Releaseから保存します。

## フォント

`assets/fonts/ReviewSans.otf` は Noto CJK 由来のローカルフォントです。著作権表示と SIL Open Font License 1.1 を含む全文は `assets/fonts/LICENSE.txt` に同梱しています。

## 公開について

GitHub Pagesで `https://kojiki-project.github.io/line-sticker-review/` に常設します。`.nojekyll` により、リポジトリ直下をそのまま配信します。
