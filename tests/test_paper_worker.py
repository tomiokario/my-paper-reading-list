import unittest

from scripts.paper_worker import normalize_github_issue_url, resolve_notion_issue_page


def notion_page(issue_number, issue_url=""):
    return {
        "id": f"page-{issue_number}-{issue_url or 'missing'}",
        "properties": {
            "GitHub Issue Number": {"type": "number", "number": issue_number},
            "GitHub Issue URL": {"type": "url", "url": issue_url or None},
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

    def test_single_missing_url_candidate_can_be_backfilled(self):
        target = notion_page(7)
        indexes = ({}, {7: [target]})

        page, reason = resolve_notion_issue_page(indexes, "owner/repo", 7)

        self.assertIs(page, target)
        self.assertEqual(reason, "number_missing_url")

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


if __name__ == "__main__":
    unittest.main()
