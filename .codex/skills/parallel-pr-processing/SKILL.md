---
name: parallel-pr-processing
description: Use when Codex needs to process multiple GitHub pull requests in parallel or in a managed queue, including PR inventory, merge conflicts, replacement PRs, preserving the original issue intent, GitHub Codex review comments, closing references, superseded PR cleanup, and post-merge branch cleanup.
metadata:
  short-description: Process multiple PRs without losing original intent
---

# Parallel PR Processing

Use this skill when multiple GitHub PRs need to be triaged, updated, merged, replaced, or closed as superseded.

Use `docs/technical/parallel-pr-workflow.md` as the detailed source of truth.

## Core Rules

- Keep one management thread responsible for PR inventory, dependency ordering, mergeability, review status, and cleanup.
- Preserve the original Issue / PR intent before changing or replacing a PR.
- Do not flatten several PRs into one integration PR unless the replacement relationship is explicit.
- Use closing references for replaced Issues, but close replaced PRs explicitly with a superseded comment.
- For every actionable review comment, either fix it or explain why it is not accepted; react and reply after handling it.
- Keep private data, Notion database IDs, tokens, PDFs, extracted text, translations, personal notes, logs, and machine-specific paths out of tracked files.
- When the user asks to process all current PRs, follow the runbook in `docs/technical/parallel-pr-workflow.md`: inventory, order, refresh against `main`, validate, run intent/fresh reviews, handle Codex comments with reactions/replies, merge, cleanup, then repeat until no target PR remains.

## Inventory

1. Check local state with `git status --short --branch`.
2. Fetch PR metadata:
   - number, title, URL
   - head branch and base branch
   - mergeability and conflict state
   - draft / ready status
   - linked Issues and closing references
   - reviews, comments, Codex review result, and status checks
3. Classify each PR:
   - ready to merge
   - needs main refresh
   - has conflicts
   - blocked by review comments
   - superseded by another PR
   - should be replaced by an integration PR

## Intent Preservation

Before modifying a PR, collect:

- original Issue body and acceptance criteria
- PR title, body, and changed files
- review comments and requested changes
- prior user decisions in the current thread
- validation profile and evidence already provided

Write a short intent note for each PR:

- what user outcome it was meant to achieve
- which files or behavior are essential
- what must not be dropped when resolving conflict
- what validation proves the original intent remains satisfied

## Conflict And Replacement Flow

When several PRs conflict in nearby files:

1. Choose an order or create an integration PR from latest `main`.
2. Bring over all non-obsolete content required by the original Issues.
3. Avoid documenting planned behavior as implemented.
4. Add a replacement section to the integration PR body:

   ```markdown
   ## 置き換える PR

   PR #NNN に内容を統合したため、以下の PR を superseded として close する。

   - #123
   - #124

   ## 対応 Issue

   Closes #122
   ```

5. Before or immediately after merge, comment on the replaced PRs with the superseded reason and close them manually. Do not rely on GitHub closing keywords to close PRs.

## Review Handling

For each actionable GitHub Codex or human review thread:

1. Decide whether the comment is valid.
2. If valid, fix it locally, rerun validation, run intent review and fresh pre PR review, commit, push, and request Codex review again.
3. If not valid, leave the code unchanged and reply with the reason.
4. React to the original review comment after it is handled.
5. Do not call the PR done until Codex review reaches `+1` / no-major-issues or the blocker is documented.

## Merge And Cleanup

After a PR is merged:

1. Switch to `main`.
2. Pull latest `origin/main`.
3. Delete the local working branch if it still exists.
4. Delete the remote branch if it still exists and was not already removed by GitHub.
5. Confirm replaced PRs are closed with a superseded comment or explicitly left open with a reason.
6. Report merged PRs, closed PRs, validation, Codex review status, and remaining risks.

After all target PRs are merged, closed, or explicitly deferred:

1. Pull latest `main`.
2. Prune merged worktrees and local branches.
3. Confirm remote branches for merged PRs are gone.
4. Re-run open PR inventory and report any remaining PRs with reasons.
