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

## 2. Configure the Notion Paper Database

Create or update the Notion `Paper Inbox` database with these required properties:

| Property | Type |
| --- | --- |
| Title | Title |
| Status | Status or Select |
| PDF URL | URL |
| Local Folder | Rich text |
| Process Tags | Multi-select |
| Error Message | Rich text |
| Last Processed | Date |

If you import GitHub Issues or sync GitHub Projects, also add:

| Property | Type |
| --- | --- |
| GitHub Issue Number | Number |
| GitHub Issue URL | URL |
| Original Issue State | Select |
| Paper Key | Rich text |
| English Title | Rich text |
| Authors | Rich text |
| Year | Number |
| Venue | Rich text |
| DOI | Rich text |
| arXiv ID | Rich text |
| Source | Rich text |
| Source URL | URL |
| Short Summary JA | Rich text |
| Reason | Rich text |
| Relevance Note | Rich text |
| Priority | Select |
| Tags | Multi-select |
| OA Status | Select |

Set `Status` options for normal operation:

- `Inbox`: newly imported candidates from Gmail Scholar alerts, manual entry, or other intake flows.
- `Later`: worth keeping, but not ready to prepare now.
- `Want to read`: ready for the CLI to prepare local files.
- `Preparing`: the CLI or Codex is working on the card.
- `Ready to read`: local reading files are ready, or the card is ready with a manual-check tag.
- `Reading`: currently being read.
- `Read`: finished.
- `Skip`: not worth reading.
- `Error`: automatic processing failed and needs review.

You can keep existing cards. Add missing properties to the database, copy values from old lowercase properties such as `status` or `local folder` into the exact property names above, and avoid recreating cards only for schema cleanup.

Create an `Error` view in Notion:

- Filter: `Status` is `Error`.
- Sort: `Last Processed` descending.
- Show at least `Title`, `Status`, `Process Tags`, `Error Message`, `PDF URL`, `Local Folder`, and `Last Processed`.

Do not paste Notion database IDs, integration tokens, local absolute paths, PDFs, extracted text, translations, or private notes into tracked files.

## 3. Prepare Private Data Storage

Create a private data directory outside this repository and set `PAPER_READING_DATA_ROOT` to that path.

The CLI will create folders like:

```text
<PAPER_READING_DATA_ROOT>\
  papers\
    paper-id\
      metadata.json
      paper.pdf
      extracted.txt
      summary.ja.md
      notes.md
  logs\
```

## 4. Add Test Papers in Notion

Add a few cards to the Notion `Paper Inbox` database.

For the first test, set one card to:

```text
Status = Want to read
PDF URL = <direct PDF URL if available>
```

## 5. Run the CLI

This section lists implemented commands only. Planned commands such as `translate` are tracked in the README and should not be used until their issues are implemented.

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
python scripts\paper_worker.py prepare --dry-run --keep-going
```

Prepare papers:

```powershell
python scripts\paper_worker.py prepare --keep-going
```

Use `--skip-download` when you want the scheduled run to create metadata and
notes but avoid downloading PDFs until you have inspected the cards manually.

Preview failed papers that would be retried:

```powershell
python scripts\paper_worker.py retry --failed --dry-run
```

Retry failed papers:

```powershell
python scripts\paper_worker.py retry --failed --keep-going
```

Show status counts:

```powershell
python scripts\paper_worker.py status
```

Inspect one Notion paper card and its local file readiness:

```powershell
python scripts\paper_worker.py show paper-id
```

`paper-id` can be a Paper Key or Notion page ID. The command prints selected Notion properties and whether expected local files such as `metadata.json`, `paper.pdf`, `extracted.txt`, `summary.ja.md`, and `translations/` exist. It does not print private file bodies or personal notes.

## 6. Schedule Background Prepare on Windows

Use Windows Scheduled Task as the initial background runner. This keeps the
public repository tool-agnostic and does not require storing Notion tokens,
database IDs, or machine-specific paths in tracked files.

Before creating the task, run the safe preview manually:

```powershell
python scripts\paper_worker.py prepare --dry-run --keep-going
```

Inspect the output and the Notion cards it would touch. Enable the scheduled
task only after the dry-run result is expected.

Create a Windows Scheduled Task with these settings:

- Trigger: a cadence you are comfortable with, such as daily or hourly.
- Program/script: `powershell.exe`
- Start in: your local clone root for this repository.
- Run only when the user is logged on, unless your local credential and storage
  setup is ready for unattended execution.

Use this action while validating the task:

```powershell
-NoProfile -ExecutionPolicy Bypass -Command "New-Item -ItemType Directory -Force (Join-Path $env:PAPER_READING_DATA_ROOT 'logs') | Out-Null; python scripts\paper_worker.py prepare --dry-run --keep-going *>> (Join-Path $env:PAPER_READING_DATA_ROOT 'logs\prepare-task.log')"
```

After the scheduled dry-run log looks correct, change the action to:

```powershell
-NoProfile -ExecutionPolicy Bypass -Command "New-Item -ItemType Directory -Force (Join-Path $env:PAPER_READING_DATA_ROOT 'logs') | Out-Null; python scripts\paper_worker.py prepare --keep-going *>> (Join-Path $env:PAPER_READING_DATA_ROOT 'logs\prepare-task.log')"
```

The task account must be able to read the local `.env` file from the repository
root. `PAPER_READING_DATA_ROOT` must also be visible to the scheduled PowerShell
process because the log path is resolved before Python loads `.env`.

Keep the log under private data storage, for example:

```text
%PAPER_READING_DATA_ROOT%\logs\prepare-task.log
```

Do not commit that log or any resolved local path.

If a run fails, check both places:

- Notion `Error` view for `Status`, `Process Tags`, `Error Message`, and
  `Last Processed`.
- `%PAPER_READING_DATA_ROOT%\logs\prepare-task.log` for the CLI output and
  stack context needed for investigation.

`prepare --keep-going` continues with other `Want to read` cards after a card
fails, but the task may still exit non-zero when any failure occurred. Failed
cards should be visible in the Notion `Error` view with investigation details.

## 7. Import Gmail Google Scholar Alerts into Notion

The current Google Scholar alert intake creates Notion paper cards, not GitHub
Issues. The Apps Script automation reads labeled Gmail messages, extracts paper
candidates, checks for duplicates in Notion, and creates `Inbox` cards in the
Notion paper database.

Keep Apps Script secrets in Script Properties:

```text
NOTION_TOKEN=
NOTION_PAPER_DATABASE_ID=
LABELS_JSON=["google-scholar"]
DRY_RUN=true
```

`NOTION_DATABASE_ID` may be used only as a local compatibility alias for
`NOTION_PAPER_DATABASE_ID`.

Before enabling writes, run the Apps Script with `DRY_RUN=true` and inspect the
logs. Dry-run mode should report the Notion cards that would be created and
leave Gmail messages unread.

After the dry-run looks correct, set `DRY_RUN=false` in Script Properties and run
the importer again. A Gmail message should be marked read only after all paper
candidates from that message are handled successfully. If Notion creation fails,
leave the message unread so the import can be retried after fixing the problem.

## 8. Migrate Legacy GitHub Issues into Notion

Older docs under `docs/legacy/` describe the previous GitHub Issues / Projects
workflow. For current operation, Notion paper cards are the source of truth. Use
these commands only when importing existing GitHub Issues into Notion:

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

- The CLI currently creates the local folder, `metadata.json`, `notes.md`, downloads `paper.pdf` when `PDF URL` is present, extracts `extracted.txt` from an available PDF, and creates a `summary.ja.md` stub.
- `prepare` refreshes `extracted.txt` from `paper.pdf` when it runs. It creates `summary.ja.md` only when the file does not already exist, so manually written summaries are not overwritten.
- If PDF text extraction fails, the CLI sets `Status = Error`, adds `pdf_text_extract_failed` and `needs_manual_check` to `Process Tags`, and records a diagnostic `Error Message`.
- `collect` creates Notion Inbox cards only; it does not download PDFs or write private data.
- `retry --failed` targets Notion cards with `Status = Error` and reuses the same preparation flow as `prepare`. It shows `Process Tags` in dry-run output, but does not yet dispatch separate recovery logic per tag.
- GitHub Projects sync uses the GitHub CLI, so `gh` must be installed and authenticated with `project`.
- Full Japanese summary generation, translation, and diagnostic display are planned in the linked issues in the README.
- Background `prepare --keep-going` operation is documented for Windows Scheduled Task in this guide.
- Notion IDs and tokens must stay in `.env` or another local-only configuration file.
- PDF files, extracted text, translations, personal notes, logs, and machine-specific paths must stay in private data storage or local-only files, not in tracked repository files.
- When reading Japanese Markdown in PowerShell, use `Get-Content -Encoding utf8`; see [PowerShell UTF-8 Reading Check](technical/powershell-utf8-reading.md).
