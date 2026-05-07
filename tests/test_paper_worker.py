import argparse
import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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


def collect_page(title, **fields):
    properties = {
        "Title": {"type": "title", "title": [{"plain_text": title}]},
        "Status": {"type": "select", "select": {"name": "Inbox"}},
    }
    for name, value in fields.items():
        if name == "Source URL":
            properties[name] = {"type": "url", "url": value}
        else:
            properties[name] = {"type": "rich_text", "rich_text": [{"plain_text": value}]}
    return {"id": f"page-{paper_worker.slugify(title)}", "properties": properties}


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

    def test_single_missing_url_candidate_resolves_by_number_for_legacy_repo(self):
        target = notion_page(7)
        indexes = ({}, {7: [target]})

        page, reason = resolve_notion_issue_page(indexes, "owner/repo", 7, legacy_number_repo="owner/repo")

        self.assertIs(page, target)
        self.assertEqual(reason, "number")

    def test_single_missing_url_candidate_is_ambiguous_for_non_legacy_repo(self):
        target = notion_page(7)
        indexes = ({}, {7: [target]})

        page, reason = resolve_notion_issue_page(indexes, "other/repo", 7, legacy_number_repo="owner/repo")

        self.assertIsNone(page)
        self.assertEqual(reason, "ambiguous_number")

    def test_single_different_repo_url_candidate_is_ambiguous(self):
        target = notion_page(7, "https://github.com/other/repo/issues/7")
        indexes = ({"https://github.com/other/repo/issues/7": [target]}, {7: [target]})

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


class DotenvTests(unittest.TestCase):
    def test_empty_dotenv_assignment_clears_existing_environment_value(self):
        env_path = Mock()
        env_path.exists.return_value = True
        env_path.read_text.return_value = "GITHUB_REPOSITORY=\n"

        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "stale/repo"}):
            paper_worker.load_dotenv(env_path)

            self.assertEqual(os.environ["GITHUB_REPOSITORY"], "")


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


class IssueImportParsingTests(unittest.TestCase):
    def test_first_url_strips_markdown_autolink_delimiters(self):
        value = "PDF: <https://arxiv.org/pdf/2601.00630>."

        self.assertEqual(paper_worker.first_url(value), "https://arxiv.org/pdf/2601.00630")

    def test_first_url_preserves_valid_autolink_trailing_characters(self):
        value = "See <https://example.com/wiki/Foo_(bar)>."

        self.assertEqual(paper_worker.first_url(value), "https://example.com/wiki/Foo_(bar)")

    def test_first_url_preserves_valid_markdown_link_trailing_parenthesis(self):
        value = "See [paper](https://example.com/wiki/Foo_(bar))."

        self.assertEqual(paper_worker.first_url(value), "https://example.com/wiki/Foo_(bar)")

    def test_parse_issue_body_accepts_colon_after_bold_key(self):
        meta = paper_worker.parse_issue_body("- **Source URL**: https://example.com/paper\n")

        self.assertEqual(meta["Source URL"], "https://example.com/paper")

    def test_parse_issue_body_accepts_colon_inside_bold_key(self):
        meta = paper_worker.parse_issue_body("- **Source URL:** https://example.com/paper\n")

        self.assertEqual(meta["Source URL"], "https://example.com/paper")

    def test_parse_issue_body_requires_colon_separator_for_bold_fields(self):
        meta = paper_worker.parse_issue_body("- **Source URL** https://example.com/paper\n")

        self.assertNotIn("Source URL", meta)

    def test_extract_doi_preserves_parenthesized_identifier(self):
        value = (
            "https://doi.org/10.1002/(SICI)1097-4571(199505)46:4"
            "%3C327::AID-ASI6%3E3.0.CO;2-0)."
        )

        self.assertEqual(
            paper_worker.extract_doi(value),
            "10.1002/(SICI)1097-4571(199505)46:4%3C327::AID-ASI6%3E3.0.CO;2-0",
        )

    def test_extract_arxiv_accepts_legacy_identifiers(self):
        self.assertEqual(paper_worker.extract_arxiv("https://arxiv.org/abs/cs/0112017"), "cs/0112017")
        self.assertEqual(paper_worker.extract_arxiv("see hep-th/9901001v2"), "hep-th/9901001")

    def test_extract_arxiv_accepts_modern_arxiv_urls(self):
        self.assertEqual(paper_worker.extract_arxiv("https://arxiv.org/abs/2601.00630v2"), "2601.00630")

    def test_extract_arxiv_accepts_explicit_modern_identifier(self):
        self.assertEqual(paper_worker.extract_arxiv("arXiv:2601.00630v2"), "2601.00630")

    def test_extract_arxiv_does_not_treat_non_arxiv_url_paths_as_legacy_ids(self):
        self.assertEqual(paper_worker.extract_arxiv("https://example.com/cs/0112017"), "")

    def test_extract_arxiv_does_not_treat_non_arxiv_url_paths_as_modern_ids(self):
        self.assertEqual(paper_worker.extract_arxiv("https://example.com/2024.12345"), "")

    def test_issue_import_uses_clean_autolink_urls_and_legacy_arxiv_id(self):
        issue = {
            "number": 7,
            "title": "Legacy arXiv paper",
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/7",
            "labels": [],
            "body": "\n".join(
                [
                    "- **Source URL**: <https://arxiv.org/abs/cs/0112017>",
                    "- **OA URL**: <https://arxiv.org/pdf/cs/0112017>",
                ]
            ),
        }

        with patch.object(paper_worker, "database_property_type", return_value="select"):
            properties = paper_worker.issue_to_properties("owner/repo", issue)

        self.assertEqual(properties["Source URL"], {"url": "https://arxiv.org/abs/cs/0112017"})
        self.assertEqual(properties["PDF URL"], {"url": "https://arxiv.org/pdf/cs/0112017"})
        self.assertEqual(
            properties["arXiv ID"],
            {"rich_text": [{"type": "text", "text": {"content": "cs/0112017"}}]},
        )
        self.assertEqual(
            properties["Paper Key"],
            {"rich_text": [{"type": "text", "text": {"content": "arxiv-cs-0112017"}}]},
        )

    def test_issue_import_uses_parenthesized_doi_for_key(self):
        issue = {
            "number": 8,
            "title": "Parenthesized DOI",
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/8",
            "labels": [],
            "body": (
                "- **Source URL**: "
                "https://doi.org/10.1002/(SICI)1097-4571(199505)46:4"
                "%3C327::AID-ASI6%3E3.0.CO;2-0)."
            ),
        }

        with patch.object(paper_worker, "database_property_type", return_value="select"):
            properties = paper_worker.issue_to_properties("owner/repo", issue)

        doi = "10.1002/(SICI)1097-4571(199505)46:4%3C327::AID-ASI6%3E3.0.CO;2-0"
        self.assertEqual(properties["DOI"], {"rich_text": [{"type": "text", "text": {"content": doi}}]})
        self.assertEqual(
            properties["Paper Key"],
            {"rich_text": [{"type": "text", "text": {"content": "doi-10.1002-sici-1097-4571-199505-46-4-3c327-aid-asi6-3e3.0.co-2-0"}}]},
        )

    def test_issue_import_does_not_use_non_arxiv_numeric_url_as_arxiv_id(self):
        issue = {
            "number": 9,
            "title": "Non arXiv numeric path",
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/9",
            "labels": [],
            "body": "- **Source URL**: https://example.com/2024.12345",
        }

        with patch.object(paper_worker, "database_property_type", return_value="select"):
            properties = paper_worker.issue_to_properties("owner/repo", issue)

        self.assertNotIn("arXiv ID", properties)
        self.assertEqual(
            properties["Paper Key"],
            {"rich_text": [{"type": "text", "text": {"content": "github-owner-repo-issue-9"}}]},
        )


class CollectCommandTests(unittest.TestCase):
    def collect_args(self, payload, dry_run=True):
        records = payload if isinstance(payload, list) else [payload]
        return (
            argparse.Namespace(input="collect.json", dry_run=dry_run),
            patch.object(paper_worker, "load_collect_input", return_value=records),
        )

    def test_collect_parser_registers_command(self):
        args = paper_worker.build_parser().parse_args(["collect", "--input", "papers.json", "--dry-run"])

        self.assertIs(args.func, paper_worker.command_collect)
        self.assertEqual(args.input, "papers.json")
        self.assertTrue(args.dry_run)

    def test_collect_dry_run_prints_planned_card_without_creating(self):
        args, input_patch = self.collect_args(
            {
                "title": "A Useful Paper",
                "source_url": "https://doi.org/10.1234/example",
                "tags": ["reading-list", "survey"],
            }
        )

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("would collect: A Useful Paper [doi-10.1234-example]", stdout.getvalue())
        self.assertIn("done: would_create=1 skipped=0", stdout.getvalue())

    def test_collect_creates_inbox_card_properties(self):
        args, input_patch = self.collect_args(
            {
                "title": "Collected Paper",
                "url": "https://example.com/collected-paper",
                "pdf_url": "https://arxiv.org/pdf/2601.00630v2",
                "arxiv_id": "2601.00630v2",
                "authors": "A. Researcher",
                "year": "2026",
                "venue": "ExampleConf",
                "summary_ja": "Short summary",
                "reason": "Looks relevant",
                "relevance_note": "Matches the project",
                "priority": "High",
                "tags": ["llm"],
                "source": "manual",
            },
            dry_run=False,
        )

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_called_once()
        properties = create_page.call_args.args[0]
        self.assertEqual(properties["Title"], {"title": [{"type": "text", "text": {"content": "Collected Paper"}}]})
        self.assertEqual(properties["Status"], {"select": {"name": "Inbox"}})
        self.assertEqual(properties["Paper Key"], {"rich_text": [{"type": "text", "text": {"content": "arxiv-2601.00630"}}]})
        self.assertEqual(properties["Source URL"], {"url": "https://example.com/collected-paper"})
        self.assertEqual(properties["PDF URL"], {"url": "https://arxiv.org/pdf/2601.00630v2"})
        self.assertEqual(properties["arXiv ID"], {"rich_text": [{"type": "text", "text": {"content": "2601.00630"}}]})
        self.assertEqual(properties["Year"], {"number": 2026})
        self.assertEqual(properties["Priority"], {"select": {"name": "High"}})
        self.assertEqual(properties["Tags"], {"multi_select": [{"name": "llm"}]})

    def test_collect_splits_comma_separated_tags(self):
        args, input_patch = self.collect_args(
            {
                "title": "Tagged Paper",
                "tags": "survey, llm",
            },
            dry_run=False,
        )

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        properties = create_page.call_args.args[0]
        self.assertEqual(properties["Tags"], {"multi_select": [{"name": "survey"}, {"name": "llm"}]})

    def test_collect_rejects_comma_in_priority_before_create(self):
        args, input_patch = self.collect_args(
            {
                "title": "Invalid Priority",
                "priority": "High,urgent",
            },
            dry_run=False,
        )

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
        ):
            with self.assertRaisesRegex(paper_worker.PaperWorkerError, "priority must not contain commas"):
                paper_worker.command_collect(args)

        create_page.assert_not_called()

    def test_collect_skips_existing_doi_duplicate(self):
        args, input_patch = self.collect_args({"title": "Duplicate Paper", "doi": "10.5555/example"})

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[collect_page("Existing", DOI="10.5555/example")]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("skipped duplicate (DOI): Duplicate Paper", stdout.getvalue())
        self.assertIn("done: would_create=0 skipped=1", stdout.getvalue())

    def test_collect_skips_existing_doi_url_duplicate(self):
        args, input_patch = self.collect_args({"title": "Duplicate Paper", "doi": "10.5555/example"})

        with (
            input_patch,
            patch.object(
                paper_worker,
                "query_database",
                return_value=[collect_page("Existing", DOI="https://doi.org/10.5555/example")],
            ),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("skipped duplicate (DOI): Duplicate Paper", stdout.getvalue())

    def test_collect_ignores_placeholder_doi_for_duplicate_key(self):
        args, input_patch = self.collect_args(
            [
                {"title": "First Placeholder DOI", "doi": "N/A"},
                {"title": "Second Placeholder DOI", "doi": "unknown"},
            ]
        )

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("would collect: First Placeholder DOI [title-first-placeholder-doi]", stdout.getvalue())
        self.assertIn("would collect: Second Placeholder DOI [title-second-placeholder-doi]", stdout.getvalue())
        self.assertIn("done: would_create=2 skipped=0", stdout.getvalue())

    def test_collect_ignores_existing_placeholder_doi(self):
        args, input_patch = self.collect_args({"title": "New Placeholder DOI", "doi": "N/A"})

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[collect_page("Existing", DOI="N/A")]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("would collect: New Placeholder DOI [title-new-placeholder-doi]", stdout.getvalue())
        self.assertIn("done: would_create=1 skipped=0", stdout.getvalue())

    def test_collect_ignores_placeholder_arxiv_for_duplicate_key(self):
        args, input_patch = self.collect_args(
            [
                {"title": "First Placeholder arXiv", "arxiv_id": "N/A"},
                {"title": "Second Placeholder arXiv", "arxiv_id": "unknown"},
            ]
        )

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("would collect: First Placeholder arXiv [title-first-placeholder-arxiv]", stdout.getvalue())
        self.assertIn("would collect: Second Placeholder arXiv [title-second-placeholder-arxiv]", stdout.getvalue())
        self.assertIn("done: would_create=2 skipped=0", stdout.getvalue())

    def test_collect_ignores_existing_placeholder_arxiv(self):
        args, input_patch = self.collect_args({"title": "New Placeholder arXiv", "arxiv_id": "N/A"})

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[collect_page("Existing", **{"arXiv ID": "N/A"})]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("would collect: New Placeholder arXiv [title-new-placeholder-arxiv]", stdout.getvalue())
        self.assertIn("done: would_create=1 skipped=0", stdout.getvalue())

    def test_collect_ignores_placeholder_source_url_for_duplicate_key(self):
        args, input_patch = self.collect_args(
            [
                {"title": "First Placeholder URL", "source_url": "N/A"},
                {"title": "Second Placeholder URL", "source_url": "unknown"},
            ]
        )

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("would collect: First Placeholder URL [title-first-placeholder-url]", stdout.getvalue())
        self.assertIn("would collect: Second Placeholder URL [title-second-placeholder-url]", stdout.getvalue())
        self.assertIn("done: would_create=2 skipped=0", stdout.getvalue())

    def test_collect_skips_existing_arxiv_version_duplicate(self):
        args, input_patch = self.collect_args({"title": "Duplicate Paper", "arxiv_id": "2601.00630"})

        with (
            input_patch,
            patch.object(
                paper_worker,
                "query_database",
                return_value=[collect_page("Existing", **{"arXiv ID": "2601.00630v2"})],
            ),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("skipped duplicate (arXiv ID): Duplicate Paper", stdout.getvalue())

    def test_collect_preserves_source_url_path_case_for_duplicate_key(self):
        args, input_patch = self.collect_args(
            [
                {"title": "Upper Path", "source_url": "https://example.test/Paper"},
                {"title": "Lower Path", "source_url": "https://example.test/paper"},
            ]
        )

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("would collect: Upper Path [url-example.test-paper-", stdout.getvalue())
        self.assertIn("would collect: Lower Path [url-example.test-paper-", stdout.getvalue())
        self.assertIn("done: would_create=2 skipped=0", stdout.getvalue())

    def test_collect_normalizes_source_url_scheme_and_host_case_for_duplicate_key(self):
        args, input_patch = self.collect_args({"title": "Duplicate Host Case", "source_url": "https://example.test/paper"})

        with (
            input_patch,
            patch.object(
                paper_worker,
                "query_database",
                return_value=[collect_page("Existing", **{"Source URL": "HTTPS://EXAMPLE.TEST/paper"})],
            ),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("skipped duplicate (Source URL): Duplicate Host Case", stdout.getvalue())

    def test_collect_uses_existing_pdf_url_for_arxiv_duplicate(self):
        args, input_patch = self.collect_args({"title": "Duplicate PDF URL", "arxiv_id": "2601.00630"})

        with (
            input_patch,
            patch.object(
                paper_worker,
                "query_database",
                return_value=[collect_page("Existing", **{"PDF URL": "https://arxiv.org/pdf/2601.00630v2"})],
            ),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("skipped duplicate (arXiv ID): Duplicate PDF URL", stdout.getvalue())

    def test_collect_uses_existing_pdf_url_for_doi_duplicate(self):
        args, input_patch = self.collect_args({"title": "Duplicate DOI PDF URL", "doi": "10.5555/example"})

        with (
            input_patch,
            patch.object(
                paper_worker,
                "query_database",
                return_value=[collect_page("Existing", **{"PDF URL": "https://doi.org/10.5555/example"})],
            ),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("skipped duplicate (DOI): Duplicate DOI PDF URL", stdout.getvalue())

    def test_collect_skips_existing_title_duplicate(self):
        args, input_patch = self.collect_args({"title": "Known Paper"})

        with (
            input_patch,
            patch.object(
                paper_worker,
                "query_database",
                return_value=[collect_page("Known   Paper", **{"Paper Key": "legacy-key"})],
            ),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("skipped duplicate (Title): Known Paper", stdout.getvalue())

    def test_collect_skips_duplicate_within_same_input_by_paper_key(self):
        args, input_patch = self.collect_args([{"title": "Same Title"}, {"title": "Same  Title"}])

        with (
            input_patch,
            patch.object(paper_worker, "query_database", return_value=[]),
            patch.object(paper_worker, "database_property_type", return_value="select"),
            patch.object(paper_worker, "create_page") as create_page,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            exit_code = paper_worker.command_collect(args)

        self.assertEqual(exit_code, 0)
        create_page.assert_not_called()
        self.assertIn("would collect: Same Title [title-same-title]", stdout.getvalue())
        self.assertIn("skipped duplicate (Paper Key): Same  Title", stdout.getvalue())


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


class PreparePageTests(unittest.TestCase):
    def test_prepare_without_pdf_url_keeps_metadata_ready_for_manual_pdf(self):
        page = notion_page(1, status="Want to read")

        with (
            patch.object(paper_worker, "paper_dir_for", return_value=Path("paper-dir")),
            patch.object(paper_worker, "write_initial_files") as write_initial_files,
            patch.object(paper_worker, "download_pdf") as download_pdf,
            patch.object(paper_worker, "update_page") as update_page,
        ):
            result = paper_worker.prepare_page(page, dry_run=False, skip_download=True)

        self.assertIn("prepared without PDF", result)
        write_initial_files.assert_called_once_with(page, Path("paper-dir"))
        download_pdf.assert_not_called()
        self.assertEqual(update_page.call_count, 2)
        final_properties = update_page.call_args_list[-1].args[1]
        self.assertEqual(final_properties["Status"], {"select": {"name": "Ready to read"}})
        self.assertEqual(
            final_properties["Process Tags"],
            {"multi_select": [{"name": "pdf_missing"}, {"name": "needs_manual_check"}]},
        )
        self.assertEqual(final_properties["Error Message"], {"rich_text": []})

    def test_prepare_skip_download_keeps_item_retryable_when_pdf_is_missing(self):
        page = {
            **notion_page(1, status="Want to read"),
            "properties": {
                **notion_page(1, status="Want to read")["properties"],
                "PDF URL": {"type": "url", "url": "https://example.com/paper.pdf"},
            },
        }
        target_dir = Path("paper-dir")

        with (
            patch.object(paper_worker, "paper_dir_for", return_value=target_dir),
            patch.object(paper_worker, "write_initial_files") as write_initial_files,
            patch.object(paper_worker, "download_pdf") as download_pdf,
            patch.object(paper_worker, "update_page") as update_page,
        ):
            result = paper_worker.prepare_page(page, dry_run=False, skip_download=True)

        self.assertIn("prepared without downloaded PDF", result)
        write_initial_files.assert_called_once_with(page, target_dir)
        download_pdf.assert_not_called()
        final_properties = update_page.call_args_list[-1].args[1]
        self.assertEqual(final_properties["Status"], {"select": {"name": "Want to read"}})
        self.assertEqual(
            final_properties["Process Tags"],
            {"multi_select": [{"name": "pdf_download_skipped"}]},
        )
        self.assertEqual(final_properties["Error Message"], {"rich_text": []})


class StatusCommandTests(unittest.TestCase):
    def test_status_counts_all_pages_by_default(self):
        args = argparse.Namespace(limit=None)

        with (
            patch.object(paper_worker, "query_database", return_value=[notion_page(1, status="Inbox")]) as query_database,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            exit_code = paper_worker.command_status(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(query_database.call_args.kwargs, {"page_size": 100, "max_results": None})

    def test_status_limit_is_only_applied_when_explicit(self):
        args = argparse.Namespace(limit=10)

        with (
            patch.object(paper_worker, "query_database", return_value=[notion_page(1, status="Inbox")]) as query_database,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            exit_code = paper_worker.command_status(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(query_database.call_args.kwargs, {"page_size": 10, "max_results": 10})


class EnvDefaultTests(unittest.TestCase):
    def test_import_github_issues_backfills_single_number_match_url(self):
        args = argparse.Namespace(repo="owner/repo", limit=1, dry_run=False)
        page = notion_page(7)
        issue = {
            "number": 7,
            "title": "Known paper",
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/7",
            "labels": [],
            "body": "",
        }

        with (
            patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}),
            patch.object(paper_worker, "github_issues", return_value=[issue]),
            patch.object(paper_worker, "notion_issue_indexes", return_value=({}, {7: [page]})),
            patch.object(paper_worker, "update_page") as update_page,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            exit_code = paper_worker.command_import_github_issues(args)

        self.assertEqual(exit_code, 0)
        update_page.assert_called_once_with(
            page["id"],
            {"GitHub Issue URL": {"url": "https://github.com/owner/repo/issues/7"}},
        )

    def test_import_github_issues_does_not_backfill_single_number_match_for_non_default_repo(self):
        args = argparse.Namespace(repo="other/repo", limit=1, dry_run=False)
        page = notion_page(7)
        issue = {
            "number": 7,
            "title": "Other paper",
            "state": "open",
            "html_url": "https://github.com/other/repo/issues/7",
            "labels": [],
            "body": "",
        }

        with (
            patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}),
            patch.object(paper_worker, "github_issues", return_value=[issue]),
            patch.object(paper_worker, "notion_issue_indexes", return_value=({}, {7: [page]})),
            patch.object(paper_worker, "update_page") as update_page,
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            exit_code = paper_worker.command_import_github_issues(args)

        self.assertEqual(exit_code, 0)
        update_page.assert_not_called()

    def test_sync_project_backfills_single_number_match_url(self):
        args = argparse.Namespace(owner="owner", project_number=2, limit=10, dry_run=False, force_status=False)
        page = notion_page(7)
        item = {
            "content": {
                "number": 7,
                "url": "https://github.com/owner/repo/issues/7",
                "title": "Known paper",
            },
        }

        with (
            patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}),
            patch.object(paper_worker, "github_project_items", return_value=[item]),
            patch.object(paper_worker, "notion_issue_indexes", return_value=({}, {7: [page]})),
            patch.object(paper_worker, "update_page") as update_page,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            exit_code = paper_worker.command_sync_github_project(args)

        self.assertEqual(exit_code, 0)
        update_page.assert_called_once_with(
            page["id"],
            {"GitHub Issue URL": {"url": "https://github.com/owner/repo/issues/7"}},
        )

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
