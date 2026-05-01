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

The current Google Scholar alert intake flow creates paper cards in Notion.
Gmail alert messages are parsed by automation, deduplicated against the Notion
paper database, and stored as `Inbox` cards for review. The older
GitHub-Issue-based intake is kept only as legacy documentation.

Notion credentials and database IDs must stay out of tracked files. Use Google
Apps Script Properties for Gmail/Scholar automation, or local-only settings such
as `.env` for CLI work.

## Getting Started

See [docs/getting-started.md](docs/getting-started.md).
