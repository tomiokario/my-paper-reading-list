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
- 文字化け、エンコーディング不整合、読めない日本語テキストなどを発見した場合は、作業対象外でも無視せず GitHub Issue として記録します。今回の発見も同じ扱いにします。

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

## 並列 PR 対応

複数 Pull Request を同時に処理する場合は、`docs/technical/parallel-pr-workflow.md` に従います。

基本方針:

- open PR を mergeability、conflict、review 状態、置き換え関係で分類する。
- PR を更新、統合、close する前に、元 Issue / 元 PR の意図と acceptance criteria を確認する。
- conflict 解消では片方の内容を機械的に捨てず、どの意図をどこに残すかを明示する。
- 置き換え PR では本文に `## 置き換える PR` 節を置き、置き換え元 PR / Issue の closing reference を書く。
- review comment へ対応した場合は、妥当性判断、修正または非対応理由、reaction、返信を thread 単位で行う。

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

## Pre PR Review Gate

GitHub 上の Codex review は最後の保険として使う。PR に出してから初めて大きな問題を見つける運用にはしない。

今後、commit / push / PR 作成または PR 更新の前に、必ず次の順で確認する。

1. intent review
   - ユーザーの依頼、会話で固まった意図、受け入れ条件を確認する。
   - 実装が「頼まれたこと」からずれていないかを見る。
2. fresh pre PR review
   - intent review を通過したあとに実施する。
   - 実装担当とは別の fresh な reviewer が、現在差分、関連 docs/tests、検証結果、public/private data 境界だけを見て確認する。
   - この差分を commit / push / PR に出してよいかを明示的に判定する。
3. commit / push / PR
   - intent review と fresh pre PR review の両方が通った場合だけ進める。

どちらかで blocker が出た場合は、修正してから該当 review を再実行する。
完了報告には、intent review と fresh pre PR review を実施したか、通過したかを書く。
## GitHub Codex Review Gate

After creating or updating a Pull Request, continue the PR work until GitHub
Codex review returns a positive result. A positive result means either a visible
`+1` / thumbs-up reaction from Codex or a Codex review/comment that says it did
not find major issues.

If Codex review returns actionable comments, requested changes, or major issues,
address them before considering the PR ready. After each fix:

1. update the implementation in the issue worktree,
2. rerun the appropriate local validation,
3. rerun intent review and fresh pre PR review for the new diff,
4. commit and push the fix,
5. ask for GitHub Codex review again.

Do not stop at PR creation when Codex review has not completed yet. Completion
reports must state whether GitHub Codex review reached `+1` / no-major-issues,
or explain why that check could not be completed.

## Pull Request Language

Pull Request titles and bodies for this repository must be written in Japanese.
Use Japanese for the summary, validation, review status, external state changes,
remaining risks, and closing issue references. Keep command names, file paths,
environment variable names, and exact tool output snippets in their original
literal form.

## Replacement Pull Requests

複数 PR の内容を統合した置き換え PR を作る場合は、置き換え元 PR を本文に明記する。

本文には以下のような節を置き、merge 時に GitHub が対象 PR / Issue を自動 close できるよう closing reference を書く。

```markdown
## 置き換える PR

PR #129 に内容を統合したため、merge 時に以下を close する。

Closes #123
Closes #124
```

すでに統合 PR を merge 済みで closing reference が自動発火しない場合は、統合先 PR の本文やコメントに記録を残し、置き換え元 PR へ superseded 理由をコメントして close する。

## Process Update Rule

Process updates come first. If the user changes the development workflow, review sequence, storage policy, or agent rules, update the canonical operating files before applying that new workflow to the current task.

Canonical operating files:

- `AGENTS.md`
- `docs/technical/parallel-issue-workflow.md`
- `.codex/agents/*`

After those files are updated, apply the new rule to the current diff and rerun the required reviews.
