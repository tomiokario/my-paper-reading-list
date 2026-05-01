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
