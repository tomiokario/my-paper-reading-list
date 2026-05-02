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

Collect candidate papers into the Notion Inbox from a local JSON file:

```powershell
python scripts\paper_worker.py collect --input candidates.json --dry-run
python scripts\paper_worker.py collect --input candidates.json
```

The initial `collect` input is either one JSON object or an array of objects. `title` is required.
Optional fields are `source_url` or `url`, `pdf_url`, `doi`, `arxiv_id`, `authors`, `year`,
`venue`, `summary_ja`, `reason`, `relevance_note`, `priority`, `tags`, and `source`.
`tags` can be a JSON array or a comma-separated string. `priority` and each tag must not contain
commas after normalization because Notion select option names do not allow commas.

Example:

```json
[
  {
    "title": "Example Paper",
    "source_url": "https://doi.org/10.1234/example",
    "pdf_url": "https://example.com/paper.pdf",
    "authors": ["A. Researcher", "B. Author"],
    "year": 2026,
    "venue": "ExampleConf",
    "summary_ja": "Short Japanese summary",
    "reason": "Why this should be considered",
    "relevance_note": "How this connects to the reading list",
    "priority": "Medium",
    "tags": ["survey"],
    "source": "manual"
  }
]
```

`collect --dry-run` queries Notion, prints cards that would be created, and prints duplicate skips
without creating pages. Duplicate checks use DOI, arXiv ID, Source URL, Paper Key, and Title against
existing Notion pages and earlier items in the same input file. New cards are created with
`Status = Inbox`. Notion tokens, database IDs, and private paper data must stay in `.env` or other
local-only files, not in `candidates.json` or tracked docs.

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
- `collect` creates Notion Inbox cards only; it does not download PDFs or write private data.
- GitHub Projects sync uses the GitHub CLI, so `gh` must be installed and authenticated with `project`.
- Full text extraction and translation are planned next.
- Notion IDs and tokens must stay in `.env` or another local-only configuration file.
