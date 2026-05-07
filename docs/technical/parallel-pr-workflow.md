# Parallel PR Workflow

このドキュメントは、この repository で複数の Pull Request を同時に処理するときの運用をまとめる。

## 基本単位

並列 PR 対応では、次を基本単位にする。

- 1 Pull Request
- 1 元 Issue または元 PR の意図
- 1 head branch
- 1 review / validation 状態

進行管理スレッドは open PR の棚卸し、依存関係、mergeability、review 状態、置き換え関係、merge 後の後片付けを管理する。

## 開始時の棚卸し

最初に以下を確認する。

```powershell
git status --short --branch
gh pr list --state open --json number,title,headRefName,baseRefName,isDraft,mergeStateStatus,mergeable,url
```

PR ごとに次を記録する。

- PR 番号、title、URL
- head branch と base branch
- draft / ready
- mergeability と conflict 状態
- linked Issue、closing reference、置き換え関係
- CI / status check
- GitHub Codex review の結果
- 未対応 review thread

## 分類

進行管理スレッドは PR を次に分類する。

- そのまま merge できる
- 最新 `main` への追従が必要
- conflict 解消が必要
- review comment 対応が必要
- ほかの PR に置き換えられる
- 統合 PR を新規作成する方が安全
- 元 Issue の意図確認が必要

同じファイルや同じ仕様境界を触る PR は、同時に別々の方向へ進めない。順番に main へ取り込むか、統合 PR で一度に整理する。

## 全 PR 処理ランブック

ユーザーが「現在届いている PR を処理して merge する」「すべての PR を merge できたら片付ける」と依頼した場合は、次を標準手順にする。

1. `git status --short --branch` と `gh pr list --state open ...` で main と open PR の状態を確認する。
2. 先に workflow / review / cleanup ルール変更が依頼されている場合は、このドキュメント、`AGENTS.md`、関連 skill を更新してから PR 処理へ進む。
3. open PR を merge しやすさ、依存関係、触るファイル、元 Issue の意図で並べる。docs-only や clean な PR を先に入れ、同じ実装ファイルを触る PR は main に取り込む順番を明示する。
4. 対象 PR ごとに元 Issue / PR 本文 / 変更ファイル / review comment を確認し、落としてはいけない intent を短く整理する。
5. 対象 PR の worktree で最新 `origin/main` を merge し、conflict があれば片方を機械的に捨てず、元 intent と main 側の既存変更を両方満たす形に直す。
6. 変更後は validation profile に沿って検証する。script 変更なら focused unit test と dry-run 相当、docs 変更なら矛盾や planned/implemented の整合を確認する。
7. commit / push の前に intent review と fresh pre PR review を行う。blocker が出た場合は修正して該当 review を再実行する。
8. push 後、妥当な review comment には `+1` reaction と返信を付け、妥当でない comment には reaction を付けず理由を返信する。
9. `@codex review` を依頼し、GitHub Codex review が `+1` / no-major-issues になるまで、指摘対応、validation、intent review、fresh pre PR review、commit、push を繰り返す。
10. PR が clean / mergeable で、最新 head に対する no-major-issues が確認できたら merge する。
11. merge 後は main を pull し、該当 worktree と local branch を削除し、remote branch が残っていれば削除する。
12. open PR inventory を取り直し、次の PR へ進む。

処理中に自分が作っていない差分や追加 commit を見つけた場合は、ユーザーまたは別エージェントの変更として扱う。巻き戻さず、対象 PR の intent に沿うか確認し、必要なら validation と review gate を通して取り込む。

## 元の意図を逃さない確認

PR を更新、置き換え、close する前に、必ず元の意図を短く整理する。

確認するもの:

- 元 Issue の本文、acceptance criteria、関連コメント
- PR 本文、変更ファイル、既存の validation
- human review / Codex review のコメント
- ユーザーが会話で追加した方針
- public/private data 境界

意図メモには次を書く。

- この PR が解決しようとしていたユーザー価値
- 統合時に落としてはいけない仕様、説明、検証観点
- 置き換え先 PR に移す内容
- 置き換えずに close してよい理由

## Conflict 解消

conflict がある PR は、原則として最新 `main` を正とする。

```powershell
git switch <pr-branch>
git fetch origin
git merge origin/main
```

docs conflict の場合は片方を捨てず、次を確認する。

- 同じ内容を二重に説明していないか
- planned item を implemented と書いていないか
- README、getting-started、spec が矛盾していないか
- 見出し番号、リンク、private data 境界が壊れていないか

実装 conflict の場合は validation profile を再確認し、既存テストだけで足りない場合は focused test を追加または実行する。

## 置き換え PR

複数 PR の内容を 1 本へ統合する場合は、統合 PR の本文に置き換え元を明記する。

```markdown
## 置き換える PR

PR #129 に内容を統合したため、以下の PR を superseded として close する。

- #123
- #124

## 対応 Issue

Closes #122
```

GitHub の closing keyword は Issue を close するための仕組みとして扱う。置き換え元 PR は自動 close を前提にせず、統合先 PR に記録を残し、置き換え元 PR に superseded コメントを残して明示的に close する。

## Review Comment 対応

GitHub Codex review や human review の指摘は、thread 単位で扱う。

1. 指摘が妥当か判断する。
2. 妥当なら修正する。
3. 妥当でないなら、修正しない理由を返信する。
4. 対応後、元コメントに reaction を付け、返信する。
5. 修正した場合は validation、intent review、fresh pre PR review を再実行する。
6. push 後に `@codex review` を再依頼し、`+1` または no-major-issues まで続ける。

review comment を確認するときは、flat comments だけで判断せず、inline review thread も確認する。

## Merge 後の後片付け

merge 後は標準 cleanup を行う。

```powershell
git switch main
git pull origin main
git branch -d <merged-branch>
git push origin --delete <merged-branch>
```

GitHub の `--delete-branch` で remote branch が削除済みの場合は、存在確認だけでよい。

置き換え元 PR がある場合は、閉じたこと、または閉じない理由を最終報告に含める。

すべての対象 PR を merge または明示的に close / defer した後は、最後に一括 cleanup を行う。

- `main` に戻り、`git pull --ff-only origin main` で最新化する。
- `git worktree list` で merge 済み PR の worktree が残っていないか確認し、残っていれば `git worktree remove` する。
- `git branch` と `git branch -r` で merge 済み branch が残っていないか確認し、残っていれば local / remote の順で削除する。
- `gh pr list --state open` で未処理 PR が残っていないか確認する。残す PR がある場合は理由を最終報告に書く。
- 最終報告には merged PR、closed / deferred PR、validation、Codex review status、cleanup 結果、残リスクを含める。

## 完了条件

- open PR の分類が済んでいる
- 対象 PR の元意図を確認している
- conflict または review comments を処理している
- validation profile に沿う検証が済んでいる
- intent review と fresh pre PR review が通っている
- PR title / body が日本語で、validation と review status を含んでいる
- 置き換え PR では置き換え元 PR と対応 Issue が本文にある
- GitHub Codex review が `+1` / no-major-issues に到達している
- merge 後 cleanup または残タスクが明記されている
