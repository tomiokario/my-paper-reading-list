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

### 必須プロパティ

Notion database には、以下のプロパティを用意する。プロパティ名はスクリプトが参照するため、大文字小文字と空白を含めてこの表に合わせる。

| Property | Notion type | 用途 |
| --- | --- | --- |
| Title | Title | 論文カードの表示名。 |
| Status | Status または Select | 論文の運用状態。新規作成時は Notion の Status 型を推奨する。既存 database が Select 型の場合も互換として扱う。 |
| PDF URL | URL | PDF を直接取得できる URL。空でもよい。 |
| Local Folder | Rich text | private data storage 内のローカル作業フォルダ。 |
| Process Tags | Multi-select | `pdf_missing`、`pdf_download_failed`、`needs_manual_check` などの処理タグ。 |
| Error Message | Rich text | 最後に失敗した処理の理由。正常終了時は空にする。 |
| Last Processed | Date | 最後に CLI または Codex が処理した日時。 |

GitHub Issue からの import や GitHub Projects sync を使う場合は、以下も必須とする。

| Property | Notion type | 用途 |
| --- | --- | --- |
| GitHub Issue Number | Number | 取り込み元 Issue 番号。 |
| GitHub Issue URL | URL | 取り込み元 Issue URL。重複検出にも使う。 |
| Original Issue State | Select | 取り込み時点の GitHub Issue state。 |
| Paper Key | Rich text | ローカルフォルダ名を安定させるためのキー。 |
| English Title | Rich text | Issue 本文などから抽出した英語タイトル。 |
| Authors | Rich text | 著者。 |
| Year | Number | 発行年。 |
| Venue | Rich text | 会議、ジャーナル、プレプリントサーバーなど。 |
| DOI | Rich text | DOI。 |
| arXiv ID | Rich text | arXiv identifier。 |
| Source | Rich text | 候補の入口や取り込み元。 |
| Source URL | URL | 論文ページ、OA ページ、Issue 本文中の参照先など。 |
| Short Summary JA | Rich text | 短い日本語概要。 |
| Reason | Rich text | なぜ候補に入ったか。 |
| Relevance Note | Rich text | 自分の関心に近そうな点。 |
| Priority | Select | 読む優先度。 |
| Tags | Multi-select | トピックや GitHub label 由来のタグ。 |
| OA Status | Select | OA 判定。`gold`、`green`、`bronze`、`hybrid`、`closed`、`unknown` を使う。 |

既存カードに互換性を持たせるため、データ移行ではカードを作り直さず、足りないプロパティを database に追加してから既存値を埋める。`Status` が Select 型の既存 database はそのまま運用できるが、新規 database では Status 型を使う。旧表記の `status`、`local folder`、`process tags`、`error message`、`last processed` などがある場合は、値をそれぞれ `Status`、`Local Folder`、`Process Tags`、`Error Message`、`Last Processed` へ移す。移行が終わるまで旧プロパティを残してもよいが、スクリプトから参照する正本は上記の英語名とする。

PDF、全文抽出テキスト、全文対訳、詳細な個人メモは Notion に置かない。これらは private data storage に保存する。

## 論文カードの状態

Notion の論文カードには `Status` を持たせる。

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

Codex は `Want to read` の論文を見つけると、処理開始時に `Preparing` に変更する。成功したら `Ready to read` に変更する。失敗したら `Error` に変更し、失敗理由を `Process Tags` と `Error Message` に残す。

`Want to read`、`Preparing`、`Ready to read`、`Error` は、ローカル準備作業の中核状態として次のように運用する。

| Status | 運用 |
| --- | --- |
| Want to read | ユーザーが準備を許可した状態。CLI の `prepare` はこの状態だけを処理対象にする。PDF URL が空でもカードは対象になり、ローカルフォルダ、metadata、notes を作る。 |
| Preparing | CLI または Codex が処理中であることを示す一時状態。開始時に `Local Folder` と `Last Processed` を更新する。 |
| Ready to read | 読むための最低限の準備が終わった状態。PDF がない場合でも、手動確認が必要なタグを残したうえで到達できる。 |
| Error | 自動処理が失敗した状態。`Process Tags`、`Error Message`、`Last Processed` を必ず更新し、Error ビューで確認できるようにする。 |

GitHub Projects sync が `Inbox`、`Later`、`Want to read` などへ戻す情報を持っていても、`Preparing`、`Ready to read`、`Reading`、`Error` のようなローカル作業状態を不用意に上書きしない。既存カードの作業状態は、ユーザーまたは明示的な再同期操作で変更する。

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

### 定期実行

初期版の定期実行方式は Windows Scheduled Task とする。Codex automation ではなく、Windows ユーザーがローカル PC 上で明示的に管理できる OS 標準のスケジューラを使う。

Scheduled Task は repository root を作業ディレクトリにして、次の CLI を実行する。

```powershell
python scripts\paper_worker.py prepare --keep-going
```

有効化前には必ず dry-run で対象カードと出力を確認する。

```powershell
python scripts\paper_worker.py prepare --dry-run --keep-going
```

安全運用として、PDF ダウンロードをまだ走らせたくない期間は `--skip-download` を併用してよい。この場合も metadata と notes の準備、Notion の状態更新、手動確認用タグの確認を行う。

実行ログは private data storage または local-only storage に保存し、public repository には置かない。推奨先は `PAPER_READING_DATA_ROOT` 配下の `logs\prepare-task.log` とする。tracked docs には token、database ID、実際の local absolute path、ログ本文を書かない。

Scheduled Task で失敗した場合は、CLI が対象カードの `Status` を `Error` にし、`Process Tags`、`Error Message`、`Last Processed` を更新する。調査時は Notion の `Error` ビューで失敗カードを確認し、同じ時刻帯の `logs\prepare-task.log` を private data storage 側で確認する。

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

### `paper-worker retry --failed` の初期版方針

`paper-worker retry --failed` は、Notion の `Status = Error` の論文カードを再実行対象にする。
`--dry-run` では Notion 更新やローカル書き込みを行わず、`would retry: <title> (<Process Tags>)`
の形式で対象と理由を表示する。

初期版では `Process Tags` ごとに別の処理エンジンへ振り分けず、`pdf_download_failed`、
`pdf_missing`、`needs_manual_check`、空タグのいずれも `prepare` と同じ準備処理を再利用する。
再実行後の `Status`、`Process Tags`、`Error Message`、`Last Processed` は既存の準備処理が更新する。

`--keep-going` を指定しない場合は最初の失敗で終了コード 1 として停止する。`--keep-going` を
指定した場合は残りの対象を続行し、最後に 1 件でも失敗があれば終了コード 1 を返す。

## CLI implementation status

This specification includes target commands that are not all implemented yet.
The current public implementation status is summarized in
[../README.md](../README.md#cli-command-status).

Implemented commands:

| Command | Current behavior |
| --- | --- |
| `status` | Shows Notion paper status counts. |
| `prepare` | Prepares `Want to read` papers by creating private local files, downloading `paper.pdf` when `PDF URL` is present, extracting `extracted.txt` from an available PDF, creating a `summary.ja.md` stub without overwriting an existing summary, and supporting dry-run, keep-going, and skip-download operation for scheduled use. |
| `collect` | Creates Notion Inbox cards from a local candidate JSON file, with dry-run support and duplicate checks by DOI, arXiv ID, Source URL, Paper Key, and Title. |
| `retry --failed` | Retries Notion cards with `Status = Error` by reusing the same preparation flow as `prepare`; dry-run lists targets with `Process Tags`, and keep-going continues after per-card failures. |
| `show paper-id` | Inspects one Notion paper card and reports expected local artifact presence without printing private file bodies or personal notes. |
| `import-github-issues` | Imports GitHub Issues into Notion paper cards. |
| `sync-github-project` | Syncs GitHub Projects status and priority into imported Notion cards. |

Implemented operational workflows:

| Workflow | Current behavior |
| --- | --- |
| background `prepare --keep-going` operation | Uses Windows Scheduled Task as the documented initial runner. The task writes logs under private data storage or local-only storage and relies on the CLI to update Notion `Error` fields on failure. |

Planned commands and dependent workflow work:

| Planned item | Tracking issue |
| --- | --- |
| Full Japanese summary generation from `extracted.txt` | future issue |
| `translate` | [#112](https://github.com/tomiokario/my-paper-reading-list/issues/112) |
| Notion Error view and schema docs | [#116](https://github.com/tomiokario/my-paper-reading-list/issues/116) |

Planned items must not be documented as available CLI behavior until their tracking
issues are implemented. Private data boundaries still apply: PDFs, extracted text,
translations, personal notes, logs, Notion database IDs, API tokens, sync state, and
machine-specific paths stay outside tracked repository files.

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

Error ビューの要件:

- view 名は `Error` とする。
- filter は `Status` が `Error` と等しいカードだけにする。
- 表示プロパティは少なくとも `Title`、`Status`、`Process Tags`、`Error Message`、`PDF URL`、`Local Folder`、`Last Processed` を含める。
- `Last Processed` の降順で並べ、直近の失敗を先頭に出す。
- このビューは失敗調査と再実行判断の入口であり、PDF、全文抽出テキスト、全文対訳、詳細メモ、Notion database ID、API token は表示にも本文にも置かない。

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

## `paper-worker collect` initial contract

`paper-worker collect` is the first CLI entry point for registering candidate papers in the Notion
Paper Inbox. It accepts a local JSON file and does not require or store PDF files, extracted text,
translation output, Notion database IDs, tokens, or private data in tracked files.

Command shape:

```powershell
python scripts\paper_worker.py collect --input candidates.json --dry-run
python scripts\paper_worker.py collect --input candidates.json
```

The input file is either a single JSON object or an array of objects. `title` is required. Optional
fields are:

```text
source_url or url
pdf_url
doi
arxiv_id
authors
year
venue
summary_ja
reason
relevance_note
priority
tags
source
```

`tags` can be a JSON array or a comma-separated string. `priority` and each normalized tag must not
contain commas because Notion select and multi-select option names do not allow commas.

Example:

```json
{
  "title": "Example Paper",
  "source_url": "https://doi.org/10.1234/example",
  "pdf_url": "https://example.com/paper.pdf",
  "authors": ["A. Researcher", "B. Author"],
  "year": 2026,
  "venue": "ExampleConf",
  "summary_ja": "Short Japanese summary",
  "reason": "Why this should be considered",
  "relevance_note": "How this connects to the reading list",
  "priority": "Medium",
  "tags": ["survey"],
  "source": "manual"
}
```

Created Notion cards use `Status = Inbox`. `Paper Key` is generated from the first available stable
identifier in this order: DOI, arXiv ID, Source URL, then title.

Duplicate policy:

- Before creating cards, `collect` indexes existing Notion pages.
- It skips candidates that match an existing page by DOI, arXiv ID, Source URL, Paper Key, or Title.
- It also adds each planned or created candidate to the in-memory index, so duplicates inside one
  input file are skipped.
- `--dry-run` still performs the duplicate check, prints `would collect` for planned cards, and
  prints `skipped duplicate` for skipped cards without creating Notion pages.
