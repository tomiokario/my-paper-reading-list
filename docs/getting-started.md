# Getting Started

This repository is public. Keep private values in local files only.

## 1. Create Local Configuration

Copy `.env.example` to `.env` and fill in:

```text
NOTION_TOKEN=
NOTION_PAPER_DATABASE_ID=
PAPER_READING_DATA_ROOT=
```

Do not commit `.env`.

For Notion access:

1. Create a Notion integration token.
2. Give that integration access to the `Paper Inbox` database.
3. Put the token in `NOTION_TOKEN`.

This repository does not store the token or database ID in tracked files.

## 2. Prepare Private Data Storage

Create a private data directory outside this repository and set `PAPER_READING_DATA_ROOT` to that path.

The CLI will create folders like:

```text
<PAPER_READING_DATA_ROOT>\
  papers\
    paper-id\
      metadata.json
      paper.pdf
      notes.md
```

## 3. Add Test Papers in Notion

Add a few cards to the Notion `Paper Inbox` database.

For the first test, set one card to:

```text
Status = Want to read
PDF URL = <direct PDF URL if available>
```

## 4. Run the CLI

Preview what would happen:

```powershell
python scripts\paper_worker.py prepare --dry-run
```

Prepare papers:

```powershell
python scripts\paper_worker.py prepare
```

Show status counts:

```powershell
python scripts\paper_worker.py status
```

Import existing GitHub Issues into Notion:

```powershell
python scripts\paper_worker.py import-github-issues --repo owner/repository --dry-run
python scripts\paper_worker.py import-github-issues --repo owner/repository
```

Sync GitHub Projects status and priority into the imported Notion cards:

```powershell
gh auth refresh -s project
python scripts\paper_worker.py sync-github-project --owner owner --project-number 2 --dry-run
python scripts\paper_worker.py sync-github-project --owner owner --project-number 2
```

## Notes

- The CLI currently creates the local folder, `metadata.json`, `notes.md`, and downloads `paper.pdf` when `PDF URL` is present.
- GitHub Projects sync uses the GitHub CLI, so `gh` must be installed and authenticated with `project`.
- Full text extraction and translation are planned next.
- Notion IDs and tokens must stay in `.env` or another local-only configuration file.
- When reading Japanese Markdown in PowerShell, use `Get-Content -Encoding utf8`; see [PowerShell UTF-8 Reading Check](technical/powershell-utf8-reading.md).
