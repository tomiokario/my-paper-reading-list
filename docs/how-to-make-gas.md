# Google ScholarのアラートをGitHub Projectsでカンバン管理する自動化システム

Google Scholarからの論文アラートメールを自動的に解析し、GitHub Issueとして起票した上で、GitHub Projects (V2) のカンバンボードでステータス管理を行うシステムについてまとめる。

従来の[スプレッドシートによるリスト管理（Cosense）](https://scrapbox.io/tomiokario/Gmail%E4%B8%8A%E3%81%A7%E3%83%A9%E3%83%99%E3%83%AB%E5%88%86%E3%81%91%E3%81%95%E3%82%8C%E3%81%9FScholar%E3%82%A2%E3%83%A9%E3%83%BC%E3%83%88%E3%81%8B%E3%82%89%E6%96%87%E7%8C%AE%E3%83%AA%E3%82%B9%E3%83%88%E3%82%92%E7%94%9F%E6%88%90%E3%81%99%E3%82%8BGoogle_Apps_Script%EF%BC%88%E8%A9%A6%E4%BD%9C%EF%BC%89)）から、視覚的なステータス管理がしやすいGitHub Projectsへ移行したものである。

## 前提条件：Gmail側の設定

本システムは、Gmail上でScholarアラートが既にラベル振り分けされていることを前提としている。
まだ設定していない場合は、以下の記事を参照してフィルタとラベルの設定を行うこと。

> **[GmailでGoogle ScholarのAlertを作者別に自動ラベル振り分けする（Cosense）](https://scrapbox.io/tomiokario/Gmail%E3%81%A7Google_Scholar%E3%81%AEAlert%E3%82%92%E4%BD%9C%E8%80%85%E5%88%A5%E3%81%AB%E8%87%AA%E5%8B%95%E3%83%A9%E3%83%99%E3%83%AB%E6%8C%AF%E3%82%8A%E5%88%86%E3%81%91%E3%81%99%E3%82%8B)**
> 特定のキーワードや著者名ごとにラベル（例: `Scholar/AuthorName` 等）が付与される状態にしておく必要がある。

---

## 1. GitHub側の準備

### 1-1. リポジトリとProjectの作成
1.  **Repository**: 論文管理用のリポジトリを作成する（Private推奨）。
2.  **Project (V2)**: 「Board」テンプレートで作成し、上記リポジトリとリンクさせる。
    * *自動追加設定*: ProjectのWorkflows設定で「Auto-add to project」が有効になっていることを確認する（通常、リポジトリをリンクさせれば自動設定される）。

### 1-2. Access Tokenの発行
GASからGitHub APIを操作するためのトークンを取得する。
* **設定場所**: [Settings > Developer settings > Tokens (classic)](https://github.com/settings/tokens)
* **権限 (Scopes)**: `repo` (Full control of private repositories) にチェックを入れる。

---

## 2. Google Apps Script (GAS) の設定

### 2-1. プロジェクト設定（スクリプトプロパティ）
コード内に認証情報を記述しないよう、以下の環境変数を設定する。

| プロパティ名 | 設定値 | 説明 |
| :--- | :--- | :--- |
| `GITHUB_TOKEN` | `ghp_xxxx...` | 手順1-2で発行したトークン |
| `GITHUB_OWNER` | `username` | GitHubのユーザー名 |
| `GITHUB_REPO` | `repo-name` | 手順1-1で作成したリポジトリ名 |
| `UNPAYWALL_EMAIL` | `email@example.com` | Unpaywall API利用のためのメールアドレス |
| `LABELS_JSON` | `["Label_A", "Label_B"]` | 検索対象のGmailラベル（JSON配列） |
| `DAYS_LOOKBACK` | `7` | 過去何日分のメールを検索するか |

※ `LABELS_JSON` には、前提条件の項で作成したGmailのラベル名を指定する。

### 2-2. スクリプトのデプロイ
ソースコードは以下のリポジトリを参照し、GASプロジェクトの `Code.gs` に反映させる。

> [GitHubリポジトリへのリンクをここに貼る]

このスクリプトは以下の処理を行う。
1.  指定ラベルの未読メールを検索・解析。
2.  DOI/arXiv ID/URLに基づきGitHub Search APIで既存Issueを検索（重複排除）。
3.  Unpaywall API等で書誌情報とOA（オープンアクセス）状況を取得。
4.  Markdown形式で整形し、GitHub Issueを作成。

---

## 3. 自動生成されるIssueのフォーマット

本システムにより作成されるIssueは以下の構造を持つ。

### タイトル
論文タイトル（英語）

### 本文 (Markdown)
* **メタデータ**: 著者、掲載誌(Venue)、発行年、OAステータス、検索元ラベル。
* **URL**: ソースURLと、PDFへの直リンク(OA URL)を分けて記載。
* **概要**: 日本語翻訳（Google翻訳経由）と、原文の英語スニペット。