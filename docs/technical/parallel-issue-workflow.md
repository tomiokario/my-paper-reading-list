
## Current Operating Flow

This section is the current source of truth for issue-to-PR operation in this repository.

1. Clarify intent
   - Read the user request, issue body, related comments, and existing repository rules.
   - Write down the intended outcome, acceptance criteria, files likely to change, and validation profile.
2. Update operating rules first when the process changes
   - If the user changes the development process, review order, storage policy, or agent workflow, update the canonical operating files first.
   - Treat `AGENTS.md`, this document, and `.codex/agents/*` as the source of truth before applying the new process to the current code change.
   - After updating the operating files, apply the new rule to the current task and review the combined diff.
3. Implement locally
   - Work in the assigned branch/worktree.
   - Keep public workflow code separate from private data.
   - Run focused validation for the changed area.
4. Run intent review
   - Use an intent reviewer that checks the implementation against the user's actual goal and conversation context.
   - Fix any mismatch before moving on.
5. Run fresh pre PR review
   - Use a fresh reviewer that did not implement the change.
   - Input only the current diff, relevant docs/tests, validation results, and public/private boundary.
   - The reviewer must answer whether the change is ready for commit / push / PR.
6. Commit and push only after both reviews pass
   - Do not create or update a PR before the intent review and fresh pre PR review pass.
   - If either review finds a blocker, fix it and rerun the relevant review first.
7. Open or update the PR
   - Include validation results and review status in the PR body.
   - Write the PR title and body in Japanese.
   - GitHub Codex review is then used as an external safety net, not as the first serious review.
8. Run GitHub Codex review to a positive result
   - After opening or updating the PR, request GitHub Codex review.
   - Continue the PR work until Codex gives a positive result: a `+1` / thumbs-up reaction, or a Codex review/comment that says it did not find major issues.
   - Do not treat PR creation alone as completion while Codex review is still pending.
9. Address PR review comments
   - For each actionable comment, react and reply after fixing or explaining.
   - Even when addressing Codex review comments, also run the local multi-agent review for the new diff before committing/pushing.
   - After fixes are pushed, request GitHub Codex review again and repeat until the positive result is reached.

Completion criteria for a worker thread:

- implementation is complete
- validation profile checks are complete
- public/private data boundary is checked
- intent review passed
- fresh pre PR review passed
- commit is created
- branch is pushed
- PR is created or updated with validation and review evidence
- PR title and body are written in Japanese
- GitHub Codex review has reached `+1` / no-major-issues, or the blocker to completing that check is documented

# Parallel Issue Workflow

このドキュメントは、この repository で複数の GitHub Issue を並列に進めるときの運用をまとめる。

## 基本単位

並列対応では、次を基本単位にする。

- 1 Issue
- 1 作業ブランチ
- 1 worktree
- 1 Codex 作業スレッド

進行管理スレッドは Issue の棚卸し、依存関係、実行順序、Pull Request 状態、merge 後の後片付けを管理する。

各作業スレッドは、割り当てられた Issue の実装、検証、commit、push、Pull Request 作成までを担当する。

## Worktree

worktree は repository 内の gitignored な `tmp/worktrees/` に作る。

```text
my-paper-reading-list/
  tmp/
    worktrees/
      issue12/
      issue13/
```

branch 名は `codex/issueNN-short-topic` を基本にする。

```bash
git checkout main
git pull --rebase origin main
git worktree add tmp/worktrees/issue12 -b codex/issue12-short-topic main
```

## Issue の分類

進行管理スレッドは open Issue を次に分ける。

- close 候補
- 仕様確認が必要なもの
- 単独実行が必要なもの
- 並列実行できるもの
- 他 Issue の完了を待つもの

public/private data 境界、Notion schema、CLI、翻訳 pipeline など、同じファイルや同じ仕様境界を触る Issue は同じ並列グループに入れない。

## Handoff

各作業スレッドには次だけを渡す。

- 対象 Issue
- 合意済み仕様
- acceptance criteria
- validation profile
- 触ってよい範囲
- 触らない範囲
- 検証コマンド
- worktree と branch 名

## 完了条件

各作業スレッドの完了条件:

- 実装が完了している
- validation profile に沿う確認が完了している
- public/private data 境界を確認している
- `git status` に意図しない差分がない
- intent review が通過している
- fresh pre PR review が通過している
- commit 済み
- push 済み
- Pull Request 作成済み

## Merge 後の後片付け

ユーザーから merge 完了の連絡を受けたら、進行管理スレッドが primary worktree で後片付けする。

```bash
git checkout main
git pull --rebase origin main
git worktree remove tmp/worktrees/issue12
git branch -d codex/issue12-short-topic
git push origin --delete codex/issue12-short-topic
git worktree prune
```

未 merge の差分や未 push の変更がある場合は削除しない。
