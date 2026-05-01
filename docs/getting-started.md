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
