# my-paper-reading-list

Tools and notes for building a personal paper-reading workflow.

The goal is to keep the public repository focused on reusable workflow code and documentation, while private paper data stays outside git.

## What This Repository Contains

- Workflow specifications
- Notion database schema notes
- CLI and automation scripts
- Configuration templates
- Tests and sample data with dummy values

## What This Repository Must Not Contain

- PDFs
- Extracted paper text
- Full translations
- Personal reading notes
- Notion database IDs
- API tokens or OAuth credentials
- Local sync state or logs
- Machine-specific paths

## Private Data Boundary

Private data should live outside this repository.

Recommended private locations:

- A local data directory configured by environment variable
- A gitignored `private/` overlay directory
- An optional separate private repository checked out locally

The public repository should still make sense without access to any private overlay.

## Current Design

See [docs/paper-reading-system-spec.md](docs/paper-reading-system-spec.md).

## CLI Command Status

Run implemented commands with:

```powershell
python scripts\paper_worker.py <command>
```

Implemented commands:

| Command | Status | Notes |
| --- | --- | --- |
| `status` | Implemented | Shows Notion paper status counts. |
| `prepare` | Implemented | Prepares `Want to read` papers by creating the private local folder, `metadata.json`, `notes.md`, and downloading `paper.pdf` when `PDF URL` is present. |
| `import-github-issues` | Implemented | Imports GitHub Issues into Notion paper cards. |
| `sync-github-project` | Implemented | Syncs GitHub Projects status and priority into imported Notion cards. |

Planned commands and workflow work:

| Planned item | Tracking issue | Notes |
| --- | --- | --- |
| `collect` | [#110](https://github.com/tomiokario/my-paper-reading-list/issues/110) | Add an entry point for candidate papers into the Notion Inbox. |
| PDF text extraction and `summary.ja.md` | [#111](https://github.com/tomiokario/my-paper-reading-list/issues/111) | Generate private extracted text and summary files after PDF download. |
| `translate` | [#112](https://github.com/tomiokario/my-paper-reading-list/issues/112) | Generate full parallel translations from private extracted text. |
| `retry --failed` | [#113](https://github.com/tomiokario/my-paper-reading-list/issues/113) | Re-run failed paper processing based on Notion status and process tags. |
| Background `prepare --keep-going` operation | [#114](https://github.com/tomiokario/my-paper-reading-list/issues/114) | Decide and document scheduled execution without storing local secrets or paths. |
| `show paper-id` | [#115](https://github.com/tomiokario/my-paper-reading-list/issues/115) | Inspect a paper card and private local file presence without printing private file bodies. |
| Notion Error view and schema docs | [#116](https://github.com/tomiokario/my-paper-reading-list/issues/116) | Document required database properties, views, and compatibility notes. |

Do not treat planned items as available CLI commands until their tracking issues are implemented. PDFs, extracted text, translations, personal notes, logs, Notion IDs, tokens, and machine-specific paths must stay outside tracked files.

## Getting Started

See [docs/getting-started.md](docs/getting-started.md).
