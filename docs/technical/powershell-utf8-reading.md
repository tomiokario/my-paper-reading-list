# PowerShell UTF-8 Reading Check

この repository の日本語 Markdown を PowerShell で確認するときは、既定読み取りに任せず UTF-8 を明示する。

```powershell
Get-Content -Encoding utf8 docs\paper-reading-system-spec.md
Get-Content -Encoding utf8 docs\technical\parallel-issue-workflow.md
```

一部だけ確認したい場合:

```powershell
Get-Content -Encoding utf8 docs\paper-reading-system-spec.md | Select-Object -First 40
```

## 文字化けを見つけたとき

日本語 Markdown が文字化けして見えた場合は、作業対象外でも無視しない。まず表示問題かファイル破損かを切り分け、再現情報を添えて GitHub Issue に記録する。

Issue に含める情報:

- 文字化けして見えたファイルパス
- 実行した PowerShell コマンド
- `Get-Content -Encoding utf8` でも再現するか
- GitHub 上の表示や別の UTF-8 対応エディタでは正常に見えるか
- private data、token、個人ローカルパスを含まない最小の抜粋

## 表示問題とファイル破損の切り分け

1. 文字化けして見えたファイルを保存し直さない。
2. UTF-8 明示で読み直す。

   ```powershell
   Get-Content -Encoding utf8 <path-to-markdown>
   ```

3. Git の差分を確認する。

   ```powershell
   git diff -- <path-to-markdown>
   git diff --check
   ```

4. GitHub 上の表示、または UTF-8 対応エディタで同じ箇所を確認する。

判断の目安:

- `Get-Content -Encoding utf8` や GitHub 上の表示が正常で、PowerShell の既定読み取りだけが崩れる場合は表示問題として扱う。
- `Get-Content -Encoding utf8`、GitHub 上の表示、`git diff` の追加行でも文字化けしている場合は、ファイル内容の破損を疑う。
- どちらか判断できない場合も Issue 化し、確認済みのコマンドと結果を本文に残す。

Issue 作成例:

```powershell
gh issue create --title "日本語 Markdown の文字化け確認: <file>" --body "PowerShell での再現手順と UTF-8 確認結果を書く"
```

private data、Notion database ID、API token、同期状態、個人ローカルパスは Issue 本文や添付に含めない。
