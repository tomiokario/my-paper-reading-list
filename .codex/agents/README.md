
## Pre PR Review Gate

When the user changes the process itself, update the operating files first, then apply the new process to the current task. Do not commit / push / PR until the updated process has been applied and reviewed.

Use these local agents before commit / push / PR:

1. `intent-review-agent`
   - Confirms the diff matches the user's actual intent and acceptance criteria.
2. `fresh-review-agent`
   - Runs after intent review.
   - Reviews the current diff with fresh eyes and decides whether it is ready for commit / push / PR.

Do not open or update a PR until both reviews pass.
When a PR review comment is addressed later, rerun the local review for the new diff before commit / push.

# Repo Local Agent Definitions

このディレクトリには、この repository の Issue 対応で使う役割分担を再利用できるようにするための定義を置きます。

- [question-agent.toml](./question-agent.toml): 仕様整理担当
- [implementation-agent.toml](./implementation-agent.toml): 実装担当
- [fresh-review-agent.toml](./fresh-review-agent.toml): 差分レビュー担当
- [intent-review-agent.toml](./intent-review-agent.toml): 趣旨適合確認担当

親オーケストレータだけがユーザーとの窓口を持ちます。各 agent は人間へ直接質問せず、親オーケストレータへ構造化した結果を返します。

この repository では、public / private data の境界を常に確認します。PDF、全文、翻訳、個人メモ、token、Notion database ID、ローカル同期状態は public repo に入れません。
