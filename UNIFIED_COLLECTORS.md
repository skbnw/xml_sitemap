# 収集リポジトリの統一先

このリポジトリ `xml_sitemap` が、媒体取得の GitHub Actions の置き場所です。

## ここで動かすもの

- 時事、共同、読売、日経、朝日サイトマップ、AP、Bloomberg、Reuters、NPR、NYT、Politico（元からこのリポジトリ）
- NHK RSS、BBC、CNN Japan、朝日 RSS
- Yahoo のトピック RSS、カテゴリ RSS、アクセスランキング、コメント、媒体一覧・主要掲載

取得したファイルは、今までと同じフォルダ名でリポジトリ直下に置きます。
Project_NewsDB は `xml_sitemap` を見てローカルへ移します。

## まだ y_body に残しているもの

Yahoo 記事 HTML の定期取得と GCS アップロードです。
Google Cloud の Workload Identity が `skbnw/y_body` に紐付いているため、
`yahoo_body_schedule.yml` の schedule はコメントアウトしています。

移すときは次を済ませてから、`yahoo_body_schedule.yml` の schedule を戻し、
`y_body` の `00_Schedule-All` を停止します。

1. `xml_sitemap` の Actions 変数に `GCP_WORKLOAD_IDENTITY_PROVIDER` と `GCP_SERVICE_ACCOUNT` を入れる
2. GCP 側の Workload Identity が `skbnw/xml_sitemap` を許可するよう更新する
3. AWS 用シークレット（`AWS_ACCESS_KEY_ID` など）と `DISCORD_WEBHOOK_URL` をこのリポジトリに作る
4. `SYNC_PAT` をこのリポジトリに作り、NHK 取得後の Project_NewsDB 更新通知を有効にする

## 意図してコピーしていないもの

- `y_body` のリポジトリ削除ワークフロー
- `Schedule-g01` から `Schedule-g16`（`00_Schedule-All` と重複）
