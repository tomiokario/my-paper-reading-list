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

- `Want to read`: ready for the CLI to prepare local files.
- `Preparing`: the CLI or Codex is working on the card.
- `Ready to read`: local reading files are ready, or the card is ready with a manual-check tag.
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
      notes.md
```

## 4. Add Test Papers in Notion

Add a few cards to the Notion `Paper Inbox` database.

For the first test, set one card to:

```text
Status = Want to read
PDF URL = <direct PDF URL if available>
```

## 5. Run the CLI

This section lists implemented commands only. Planned commands such as `collect`, `translate`, `retry --failed`, and `show paper-id` are tracked in the README and should not be used until their issues are implemented.

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

## 6. Import Gmail Google Scholar Alerts into Notion

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

## 7. Migrate Legacy GitHub Issues into Notion

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

- The CLI currently creates the local folder, `metadata.json`, `notes.md`, and downloads `paper.pdf` when `PDF URL` is present.
- GitHub Projects sync uses the GitHub CLI, so `gh` must be installed and authenticated with `project`.
- Full text extraction, summary generation, translation, retry, diagnostic display, and background operation are planned in the linked issues in the README.
- Notion IDs and tokens must stay in `.env` or another local-only configuration file.
- PDF files, extracted text, translations, personal notes, logs, and machine-specific paths must stay in private data storage or local-only files, not in tracked repository files.
- When reading Japanese Markdown in PowerShell, use `Get-Content -Encoding utf8`; see [PowerShell UTF-8 Reading Check](technical/powershell-utf8-reading.md).
