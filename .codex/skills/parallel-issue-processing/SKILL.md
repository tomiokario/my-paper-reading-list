---
name: parallel-issue-processing
description: Use when the user wants Codex to process multiple GitHub issues in parallel using a management thread, per-issue Codex threads, git worktrees, separate branches, pull requests, and post-merge cleanup.
metadata:
  short-description: Run multiple issues in parallel with worktrees
---

# Parallel Issue Processing

この skill は、複数の GitHub Issue を同時に進めるときに使う。

詳細は `docs/technical/parallel-issue-workflow.md` を正本として確認する。

## 基本方針

- 進行管理スレッドが Issue 一覧、依存関係、並列グループ、Pull Request 状態を管理する
- 各作業スレッドは 1 Issue だけを担当する
- worktree は repo 内の gitignored な `tmp/worktrees/issueNN` に作る
- public/private data 境界を常に確認する
- close してよい Issue は理由を整理し、実際の close は人間が行う

## 手順

1. `git status --short --branch` と `git worktree list --porcelain` を確認する
2. open Issue を取得する
3. close 候補、仕様確認、単独実行、並列実行、順番待ちに分類する
4. 並列実行できる Issue ごとに `codex/issueNN-short-topic` branch と `tmp/worktrees/issueNN` worktree を作る
5. 各作業スレッドへ対象 Issue、acceptance criteria、validation profile、worktree、branch、触ってよい範囲、検証コマンドを渡す
6. 実装、検証、レビュー、commit、push、Pull Request 作成を行う
7. merge 後に進行管理スレッドが worktree と branch を後片付けする
