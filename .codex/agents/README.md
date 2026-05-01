# Repo Local Agent Definitions

このディレクトリには、この repository の Issue 対応で使う役割分担を再利用できるようにするための定義を置きます。

- [question-agent.toml](./question-agent.toml): 仕様整理担当
- [implementation-agent.toml](./implementation-agent.toml): 実装担当
- [fresh-review-agent.toml](./fresh-review-agent.toml): 差分レビュー担当
- [intent-review-agent.toml](./intent-review-agent.toml): 趣旨適合確認担当

親オーケストレータだけがユーザーとの窓口を持ちます。各 agent は人間へ直接質問せず、親オーケストレータへ構造化した結果を返します。

この repository では、public / private data の境界を常に確認します。PDF、全文、翻訳、個人メモ、token、Notion database ID、ローカル同期状態は public repo に入れません。
