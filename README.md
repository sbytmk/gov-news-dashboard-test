# 官公庁ニュースダッシュボード

67インチモニター掲示用 / 国内油脂製造業 生産管理部門向け

## 概要

経産省・農水省・国交省・厚労省・財務省・環境省の公式RSSを自動収集し、油脂製造業の業務影響度で自動分類して大型モニターに表示するダッシュボードです。

## 特徴

- **GitHub Pages配信**: サーバー不要、無料運用
- **静的JSON配信**: 表示時にRSS取得しないので読み込み一瞬
- **更新は朝6時・昼12時の月〜金のみ**: GitHub Actionsで自動取得・コミット
- **業務影響度自動判定**: 油脂業に直結するキーワード(大豆/菜種/パーム/為替/脱炭素/労働災害など)を含むニュースを左カラムに優先表示
- **キーワードハイライト**: タイトル内の重要キーワードを色分け強調
- **キーワードティッカー**: 上部に出現頻度の高いキーワードを横スクロール表示
- **完全ノーオペレーション**: クリック不要、自動スクロール、自動再読込

## 構成

```
gov-news-dashboard/
├── index.html              # メイン画面
├── style.css               # スタイル (67インチ4K想定、vw単位)
├── app.js                  # 表示制御
├── data/
│   └── news.json           # GitHub Actionsが更新するデータ
├── scripts/
│   └── fetch_news.py       # RSS取得スクリプト
└── .github/
    └── workflows/
        └── fetch-news.yml  # 朝6時/昼12時 月-金 実行
```

https://github.com/sbytmk/gov-news-dashboard-test

## デプロイ手順

### 1. GitHub リポジトリ作成

新規リポジトリ(例: `gov-news-dashboard`)を作成し、本フォルダ一式をプッシュ。

```bash
cd gov-news-dashboard
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/<ユーザー名>/gov-news-dashboard.git
git branch -M main
git push -u origin main
```

### 2. GitHub Pages 有効化

リポジトリの **Settings > Pages** で:
- Source: `Deploy from a branch`
- Branch: `main` / `/ (root)`
- Save

数分後に `https://<ユーザー名>.github.io/gov-news-dashboard/` で公開されます。

### 3. GitHub Actions 権限設定

**Settings > Actions > General > Workflow permissions** で:
- ✅ `Read and write permissions` を選択
- Save

これでActionsが`data/news.json`を自動コミットできるようになります。

### 4. 初回テスト実行

**Actions** タブから `Fetch Government News` ワークフローを選択し、`Run workflow` で手動実行。
成功すれば `data/news.json` が更新され、ダッシュボードに最新ニュースが表示されます。

## モニター掲示設定

ダッシュボードを巡回表示する場合、URLを既存の表示ローテーションに登録するだけ。
読み込み速度: JSON単一ファイル(数十KB)なので**1秒以内**に表示完了。

### ブラウザフルスクリーン表示

掲示用PCで以下のいずれか:
- `F11` キーでフルスクリーン
- Chrome起動オプション: `--kiosk https://<ユーザー名>.github.io/gov-news-dashboard/`

## カスタマイズ

### キーワード追加・変更

`app.js` の `KEYWORDS` オブジェクトを編集:

```javascript
const KEYWORDS = {
  critical: ['大豆', '菜種', ...],  // 業務直結 → ハイライト橙
  high: ['貿易', '為替', ...],       // 重要 → ハイライト黄
  medium: ['製造業', 'DX', ...],     // 関連 → 影響度中
};
```

### RSS フィード追加

`scripts/fetch_news.py` の `RSS_FEEDS` リストに追加。
`app.js` の `SOURCE_LABELS` と `style.css` の `.source-xxx` も対応追加。

### 更新時刻変更

`.github/workflows/fetch-news.yml` の cron 設定を編集。
**注意**: GitHub ActionsはUTC基準。JST = UTC+9 で逆算が必要。

| JST | UTC | cron |
|---|---|---|
| 月-金 06:00 | 日-木 21:00 | `0 21 * * 0-4` |
| 月-金 12:00 | 月-金 03:00 | `0 3 * * 1-5` |

## 想定運用

- 朝6:00: 出勤前に最新ニュースが揃う
- 昼12:00: 午前中のニュースを反映
- 土日: 更新なし(週末の更新は月曜朝に反映)
- データ保持: 直近2週間分(`fetch_news.py` の `cutoff` で調整可)

## トラブルシューティング

**Q. ニュースが表示されない**
- ブラウザのF12コンソールでエラー確認
- `data/news.json` がリポジトリにコミットされているか
- GitHub Pagesのデプロイが完了しているか (Settings > Pages)

**Q. RSS取得が失敗する**
- Actions の実行ログ確認
- 各省庁のRSSフィードURLが変更されていないか確認

**Q. キャッシュで古い内容が表示される**
- `app.js` でタイムスタンプ付きfetchを行っているが、ブラウザ強リロード(`Ctrl+Shift+R`)で確実に更新
