# 論文読書支援システム 仕様書ドラフト

## 目的

このシステムの目的は、読むべき論文を低コストに見つけ、興味を持った論文をすぐ読める状態にし、必要に応じて翻訳・メモ・関連論文整理まで進められる環境を作ることである。

中心に置く体験は「論文を読むこと」であり、GitHub Issue やスクリプト運用そのものを中心にしない。

## 全体像

このシステムでは、論文を選ぶ操作は Notion で行い、PDF取得、ファイル作成、翻訳ツールの実行などは Codex がローカル環境で行う。

```text
論文候補を集める
  ↓
Notion に論文カードが作られる
  ↓
ユーザーが Notion で読むかどうかを判断する
  ↓
「読む」と判断した論文だけ、Codex がローカル環境で下準備する
  ↓
PDF、全文対訳、メモ用ファイルをローカルに保存する
  ↓
Notion に「読む準備ができた」「処理に失敗した」などの状態を反映する
```

GitHub は、この仕組み自体を開発・改善するために使う。Codex は、ローカル作業の実行と仕組みの改善の両方を担当する。

## 使うもの

| 使うもの | 役割 |
| --- | --- |
| Notion | 論文候補を見る、読むかどうかを判断する、準備状況を見る。 |
| private data storage | PDF、抽出テキスト、全文対訳、メモ、処理ログを保存する。public repository には置かない。 |
| Codex | Notion を確認し、読む対象の論文についてローカル作業を進める。必要なスクリプトの開発・修正も行う。 |
| CLI | Codex が使う実行手段。PDF取得、翻訳、再実行、状態確認などの定型作業を行う。 |
| GitHub repository | スクリプト、仕様書、設定例、開発タスクを管理する。 |

## 普段の使い方

1. ユーザーは Notion の論文一覧を見る。
2. 論文カードの概要を見て、読むかどうかを判断する。
3. 読みたい論文の状態を `Want to read` にする。
4. Codex が、その論文を準備対象として拾う。
5. Codex が CLI や専用スクリプトを使って、PDF 取得、metadata 保存、notes.md 作成、全文対訳生成を行う。
6. 処理が終わったら、Notion の状態が `Ready to read` になる。
7. ユーザーはローカルフォルダにある PDF、対訳、メモを使って読む。
8. 処理に失敗した場合は、Notion の状態が `Error` になり、失敗理由が記録される。
9. 詳しく調べたいときや失敗したときは、Codex にログ調査や修正を依頼する。

## Notion の論文カード

Notion では、論文1本を1つのカードとして扱う。

論文カードには、読むかどうかを判断するための軽量な情報だけを置く。

- title
- authors
- year
- venue
- source
- DOI
- arXiv ID
- PDF URL
- 3行概要
- なぜ候補に入ったか
- 自分の関心に近そうな点
- priority
- tags
- status
- GitHub Issue Number
- GitHub Issue URL
- Original Issue State
- OA Status
- local folder
- process tags
- error message
- last processed

PDF、全文抽出テキスト、全文対訳、詳細な個人メモは Notion に置かない。これらは private data storage に保存する。

## 論文カードの状態

Notion の論文カードには `status` を持たせる。

| Status | 意味 |
| --- | --- |
| Inbox | 新しく入ってきた候補。まだ読むか判断していない。 |
| Later | 今すぐ読まないが、候補として残す。 |
| Want to read | 読みたい。Codex が下準備を行う対象。 |
| Preparing | Codex が PDF 取得、metadata 保存、対訳生成などを進めている。 |
| Ready to read | 読む準備ができた。ローカルフォルダに必要なファイルがある。 |
| Reading | 読書中。 |
| Read | 読了。 |
| Skip | 読まない。 |
| Error | 自動処理に失敗した。確認が必要。 |

`Want to read` は、ユーザーが「この論文は読む価値がありそうなので、PDF取得や対訳生成まで進めてよい」と判断した印である。

Codex は `Want to read` の論文を見つけると、処理開始時に `Preparing` に変更する。成功したら `Ready to read` に変更する。失敗したら `Error` に変更し、失敗理由を `process tags` と `error message` に残す。

## Public repository と private data の境界

この public repository は、仕組みを開発するための場所である。

public repository に置くもの:

- scripts
- docs
- schema
- tests
- dummy sample data
- configuration templates

public repository に置かないもの:

- PDF
- 抽出テキスト
- 全文対訳
- 詳細な個人メモ
- Notion database ID
- API token
- local sync state
- logs
- machine-specific paths

private data は、この repository の外に置く。

候補:

- 環境変数 `PAPER_READING_DATA_ROOT` で指定するローカル保存先
- gitignore された `private/` overlay
- 手元だけで clone する別の private repository

public repository の main branch には、private repository の URL や submodule 定義を入れない。必要なら、手元の `private/` 以下に別 repository を置いて運用する。

## Private data storage

PDF、抽出テキスト、全文対訳、メモ、処理ログは private data storage に保存する。

保存先は `PAPER_READING_DATA_ROOT` で指定する。

想定構造:

```text
<PAPER_READING_DATA_ROOT>\
  papers\
    paper-id\
      metadata.json
      paper.pdf
      extracted.txt
      summary.ja.md
      notes.md
      translations\
        parallel.md
        chunks\
  sync-state\
    notion.json
  logs\
  exports\
```

`paper-id` は DOI、arXiv ID、またはそれらがない場合に生成する安定したIDを使う。

## Codex によるローカル作業

Codex は、Notion とローカル保存領域をつなぐローカル作業を担当する。

Codex が毎回すべてを手作業で行うのではなく、PDF取得、metadata保存、全文対訳生成などの定型作業は CLI や専用スクリプトとして実装する。Codex はそれらを実行し、失敗した場合はログを読んで原因を調べ、必要ならスクリプトを修正する。

主な作業は以下。

### 候補の登録

Google Scholar alert、Gmail、arXiv、手動入力などから候補論文を見つけ、Codex が Notion に `Inbox` の論文カードを作る。

同じ DOI、arXiv ID、URL、タイトルの論文が既にある場合は重複登録しない。

### 読む準備

Codex が Notion で `Want to read` になっている論文を探し、ローカルフォルダを作る。

最初に必ず行う作業:

- metadata.json を作る。
- notes.md を作る。
- PDF URL がある場合は PDF を取得する。
- Notion に local folder を反映する。

PDF が取得できた場合に行う作業:

- PDF からテキストを抽出する。
- 日本語概要を作る。
- 全文対訳を生成する。

### 全文対訳

`Want to read` になった論文は、原則として全文対訳を生成する。

翻訳の本文生成は、Codex が直接行うのではなく、専用スクリプトと翻訳 AI/API を使う。既存の `parallelTranslationGenerator2` の考え方を流用・発展させる。

対訳結果はローカルフォルダに保存する。Notion には全文対訳を保存しない。

### 関連論文整理

将来的には、読了論文や候補論文との関連性を整理する。

最初は以下の情報から近さを推定する。

- authors
- venue
- keywords
- abstract
- references
- tags

最終的には、「この論文を読むなら先に読むとよい論文」「過去に読んだ論文との関係」「似た手法の論文」などを提示できるようにする。

## CLI

専用の管理画面は作らない。

状態確認、再実行、失敗調査は Codex が CLI を使って行う。

想定コマンド:

```text
paper-worker collect
paper-worker import-github-issues
paper-worker sync-github-project
paper-worker prepare
paper-worker translate
paper-worker retry --failed
paper-worker status
paper-worker show paper-id
```

ユーザーが困った場合は、Codex に CLI の出力やログを確認させて修正を依頼する。

## エラー処理

処理に失敗した場合、Codex または Codex が実行するスクリプトは Notion の論文カードを更新する。

例:

```text
Status = Error
Process Tags = translation_failed
Error Message = DeepL rate limit on chunk 12
Last Processed = 2026-05-01 11:30
```

Notion には `Error` の論文だけを見るビューを作る。

詳細確認や再実行は Codex が CLI を使って行う。

## GitHub と Codex の役割

GitHub repository は、この仕組み自体を開発・改善する場所とする。

置くもの:

- scripts
- docs
- schema
- tests
- sample metadata
- Codex に渡す task file

置かないもの:

- PDF
- 全文抽出テキスト
- 全文翻訳
- 詳細な個人メモ

Codex は以下に使う。

- Notion 上で `Want to read` になった論文の準備
- スクリプトの実装
- Notion 同期の実装
- PDF 処理の改善
- 翻訳処理の改善
- 関連論文整理の改善
- エラーログの調査
- 運用ドキュメントの整備

## 最初に作る範囲

最初は、運用が回る最小限の範囲に絞る。

1. Notion に論文カード用 database を作る。
2. 候補論文を手動または Codex で Notion に入れる。
3. Notion で `Want to read` にした論文を Codex が検知する。
4. ローカル論文フォルダを作る。
5. metadata.json と notes.md を作る。
6. PDF URL がある場合は PDF を取得する。
7. Notion に local folder と status を反映する。

この段階では、全文対訳、関連論文整理、高度な概要生成は後回しにする。ただし、後から全文対訳を追加しやすいようにフォルダ構造と status は最初から用意する。

## その後に追加する作業

運用が安定したら、以下を順に追加する。

- abstract から日本語概要を作る。
- PDF からテキストを抽出する。
- 全文対訳を作る。
- 読む優先度の候補を出す。
- 関連論文を整理する。
- 失敗した作業をまとめて再実行しやすくする。
- Codex に渡しやすい task markdown を作る。

## 未確定事項

以下は相談しながら決める。

1. 候補論文の主な入口を何にするか。
   - Google Scholar alert
   - Gmail
   - arXiv query
   - 手動追加
2. 翻訳 AI/API は何を使うか。
   - DeepL
   - OpenAI API
   - ローカル翻訳モデル
   - 既存の `parallelTranslationGenerator2`
3. 全文対訳をどの粒度で保存するか。
   - 1つの Markdown
   - section ごとの Markdown
   - chunk ごとの Markdown と統合版
4. Notion に保存する概要は、どこまでなら十分か。
5. Codex によるローカル作業は手動依頼にするか、定期的に確認する運用にするか。
6. PDF 取得は OA のみとするか、ユーザーが手動で入れた PDF も対象にするか。
7. 関連論文整理はいつから必要か。
