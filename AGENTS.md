# Codex Working Agreement

このリポジトリに対する AI エージェント向けの作業ルールは、この `AGENTS.md` を正本とします。

## 基本方針

- 応答とユーザーへの報告は日本語で行います。
- この repository は public な workflow / automation 開発用 repository として扱います。
- PDF、抽出テキスト、全文対訳、個人メモ、Notion database ID、API token、同期状態、ローカルパスは commit しません。
- private data は repository 外、または gitignored な `private/` / `data/` / `sync-state/` / `logs/` に置きます。
- `.env` や `*.local.*` は読み取り・変更・commit を避けます。必要な値はユーザーがローカルで設定します。
- public repo だけを見ても意味が通るように、private overlay 前提の説明を書きません。

## 作業フロー

- 作業開始時に `git status --short --branch` を確認します。
- 既存差分を勝手に巻き戻しません。
- 原則として `main` に直接 commit / push せず、`codex/` prefix の作業ブランチを使います。
- push 前に、秘密情報、個人パス、生成データ、private overlay が差分に混ざっていないか確認します。
- 変更後は、変更種類に合った検証を行い、完了報告で確認結果を明記します。

## Issue 対応のマルチエージェント運用

Issue に対応するときは、以下の役割分担を使います。

- 親オーケストレータ: ユーザーとの窓口、方針合意、進行管理、最終報告を担当する。
- 質問担当: Issue 本文や関連コメントから不足仕様、変更タイプ、検証観点、受け入れ条件を整理する。
- 実装担当: 合意済み仕様に従って実装し、検証結果と evidence handoff を返す。
- fresh review 担当: Issue 本文・関連コメント・現在差分だけを見て、要求とのズレや検証不足を確認する。
- intent review 担当: ユーザーとの会話で得た一次情報をもとに、実装が趣旨に沿っているか確認する。

再利用用の役割定義は `.codex/agents/*.toml` を正本とします。

実際の subagent 起動では、親オーケストレータが role、instructions、出力形式を同等設定へ写して使います。

## 並列 Issue 対応

複数 Issue を並列に進める場合は、`docs/technical/parallel-issue-workflow.md` に従います。

基本単位:

- 1 Issue
- 1 作業ブランチ
- 1 worktree
- 1 Codex 作業スレッド

worktree は repository 内の gitignored な `tmp/worktrees/` に作ります。

## Validation Profiles

変更タイプごとの主な確認観点:

- `script-cli`: CLI 入出力、dry-run、エラー時の Notion 更新、private data を public repo に混ぜないこと。
- `notion-schema`: database schema、ビュー、既存カードとの互換性、ID/token を tracked files に書かないこと。
- `paper-data-import`: 重複検出、GitHub Issue URL/番号の保持、本文メタデータの抽出、private 情報の扱い。
- `translation-pipeline`: 入力PDF、抽出テキスト、翻訳API設定、失敗時の再実行性、成果物を private data storage に保存すること。
- `docs-process`: README、仕様書、手順書、agent 定義の整合。
- `infra-config`: `.gitignore`、`.env.example`、local-only 設定、CIや実行環境の再現性。

## 完了報告

完了報告には、次を含めます。

- 変更内容
- 実行した検証
- Notion や GitHub など外部状態を変更した場合、その内容
- 未実施の確認や残リスク
- fresh review / intent review を実施したか。未実施の場合は理由
