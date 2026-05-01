import argparse
import io
import os
import unittest
from unittest.mock import patch

import scripts.paper_worker as paper_worker
from scripts.paper_worker import normalize_github_issue_url, resolve_notion_issue_page


def notion_page(issue_number, issue_url="", status="", status_type="select"):
    status_property = {"type": "status", "status": {"name": status} if status else None}
    if status_type == "select":
        status_property = {"type": "select", "select": {"name": status} if status else None}
    return {
        "id": f"page-{issue_number}-{issue_url or 'missing'}",
        "properties": {
            "GitHub Issue Number": {"type": "number", "number": issue_number},
            "GitHub Issue URL": {"type": "url", "url": issue_url or None},
            "Status": status_property,
        },
    }


class GitHubIssueResolutionTests(unittest.TestCase):
    def test_normalizes_github_issue_urls(self):
        url = "https://www.github.com/Owner/Repo/issues/7?x=1#note"
        self.assertEqual(normalize_github_issue_url(url), "https://github.com/owner/repo/issues/7")

    def test_resolves_by_url_before_issue_number(self):
        target = notion_page(7, "https://github.com/owner/repo/issues/7")
        other_repo = notion_page(7, "https://github.com/other/repo/issues/7")
        indexes = (
            {
                "https://github.com/owner/repo/issues/7": [target],
                "https://github.com/other/repo/issues/7": [other_repo],
            },
            {7: [target, other_repo]},
        )

        page, reason = resolve_notion_issue_page(indexes, "owner/repo", 7)

        self.assertIs(page, target)
        self.assertEqual(reason, "url")

    def test_single_missing_url_candidate_is_ambiguous(self):
        target = notion_page(7)
        indexes = ({}, {7: [target]})

        page, reason = resolve_notion_issue_page(indexes, "owner/repo", 7)

        self.assertIsNone(page)
        self.assertEqual(reason, "ambiguous_number")

    def test_empty_repo_does_not_match_missing_url_candidate(self):
        target = notion_page(7)
        indexes = ({}, {7: [target]})

        page, reason = resolve_notion_issue_page(indexes, "", 7)

        self.assertIsNone(page)
        self.assertEqual(reason, "ambiguous_number")

    def test_multiple_number_candidates_are_ambiguous_without_matching_url(self):
        indexes = ({}, {7: [notion_page(7), notion_page(7)]})

        page, reason = resolve_notion_issue_page(indexes, "owner/repo", 7)

        self.assertIsNone(page)
        self.assertEqual(reason, "ambiguous_number")

    def test_duplicate_issue_urls_are_ambiguous(self):
        url = "https://github.com/owner/repo/issues/7"
        indexes = ({url: [notion_page(7, url), notion_page(7, url)]}, {7: []})

        page, reason = resolve_notion_issue_page(indexes, "owner/repo", 7)

        self.assertIsNone(page)
        self.assertEqual(reason, "duplicate_url")


class NotionQueryTests(unittest.TestCase):
    def test_query_database_clamps_page_size_to_notion_limit(self):
        calls = []

        def fake_notion_request(method, path, payload):
            calls.append(payload.copy())
            return {"results": [], "has_more": False}

        with (
            patch.object(paper_worker, "require_env", return_value="database-id"),
            patch.object(paper_worker, "notion_request", side_effect=fake_notion_request),
        ):
            paper_worker.query_database(page_size=500)

        self.assertEqual(calls[0]["page_size"], 100)

    def test_query_database_uses_smaller_max_results_for_first_page(self):
        calls = []

        def fake_notion_request(method, path, payload):
            calls.append(payload.copy())
            return {"results": [], "has_more": False}

        with (
            patch.object(paper_worker, "require_env", return_value="database-id"),
            patch.object(paper_worker, "notion_request", side_effect=fake_notion_request),
        ):
            paper_worker.query_database(page_size=500, max_results=10)

        self.assertEqual(calls[0]["page_size"], 10)


class ProjectItemUpdateTests(unittest.TestCase):
    def test_project_status_mapping_accepts_github_casing(self):
        page = notion_page(7, status="Inbox")
        item = {"status": "In Progress"}

        properties = paper_worker.project_item_update_properties(item, page, force_status=False)

        self.assertEqual(properties["Status"], {"select": {"name": "Reading"}})

    def test_project_status_update_uses_native_status_property(self):
        page = notion_page(7, status="Inbox", status_type="status")
        item = {"status": "In Progress"}

        properties = paper_worker.project_item_update_properties(item, page, force_status=False)

        self.assertEqual(properties["Status"], {"status": {"name": "Reading"}})


class PrepareCommandTests(unittest.TestCase):
    def test_prepare_uses_native_status_filter_when_schema_requires_it(self):
        args = argparse.Namespace(limit=2, dry_run=True, skip_download=False, keep_going=False)

        with (
            patch.object(paper_worker, "database_property_type", return_value="status"),
            patch.object(paper_worker, "query_database", return_value=[]) as query_database,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            exit_code = paper_worker.command_prepare(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            query_database.call_args.args[0],
            {"property": "Status", "status": {"equals": "Want to read"}},
        )

    def test_keep_going_still_returns_failure_after_any_failed_item(self):
        pages = [notion_page(1), notion_page(2)]
        args = argparse.Namespace(limit=2, dry_run=False, skip_download=False, keep_going=True)

        with (
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "query_database", return_value=pages),
            patch.object(paper_worker, "prepare_page", side_effect=[RuntimeError("boom"), "prepared"]) as prepare_page,
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            exit_code = paper_worker.command_prepare(args)

        self.assertEqual(exit_code, 1)
        self.assertEqual(prepare_page.call_count, 2)


class EnvDefaultTests(unittest.TestCase):
    def test_import_github_issues_treats_empty_repository_env_as_default(self):
        args = argparse.Namespace(repo=None, limit=1, dry_run=True)

        with (
            patch.dict(os.environ, {"GITHUB_REPOSITORY": ""}),
            patch.object(paper_worker, "github_issues", return_value=[]) as github_issues,
            patch.object(paper_worker, "notion_issue_indexes", return_value=({}, {})),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            exit_code = paper_worker.command_import_github_issues(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(github_issues.call_args.args[0], "tomiokario/my-paper-reading-list")

    def test_sync_project_treats_empty_project_number_env_as_default(self):
        args = argparse.Namespace(owner=None, project_number=None, limit=10, dry_run=True, force_status=False)

        with (
            patch.dict(os.environ, {"GITHUB_PROJECT_OWNER": "", "GITHUB_PROJECT_NUMBER": ""}),
            patch.object(paper_worker, "github_project_items", return_value=[]) as github_project_items,
            patch.object(paper_worker, "notion_issue_indexes", return_value=({}, {})),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            exit_code = paper_worker.command_sync_github_project(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(github_project_items.call_args.args, ("tomiokario", 2, 10))


if __name__ == "__main__":
    unittest.main()
