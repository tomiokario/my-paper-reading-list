#!/usr/bin/env python3
"""Minimal Notion-to-local paper preparation CLI.

This script intentionally keeps private values in environment variables:

- NOTION_TOKEN
- NOTION_PAPER_DATABASE_ID
- PAPER_READING_DATA_ROOT
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any


NOTION_VERSION = os.environ.get("NOTION_VERSION", "2022-06-28")
DATABASE_PROPERTY_TYPES: dict[str, str] | None = None

PROJECT_STATUS_MAP = {
    "backlog": "Inbox",
    "pending": "Later",
    "ready": "Want to read",
    "in progress": "Reading",
    "done": "Read",
}

PROJECT_PRIORITY_MAP = {
    "P0": "High",
    "P1": "High",
    "P2": "Medium",
    "P3": "Low",
}

LOCAL_WORK_STATUSES = {"Preparing", "Ready to read", "Reading", "Error"}
DEMOTING_PROJECT_TARGETS = {"Inbox", "Later", "Want to read"}


class PaperWorkerError(RuntimeError):
    pass


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise PaperWorkerError(f"Missing required environment variable: {name}")
    return value


def env_or_default(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def env_int_or_default(name: str, default: int) -> int:
    value = env_or_default(name, str(default))
    try:
        return int(value)
    except ValueError as exc:
        raise PaperWorkerError(f"{name} must be an integer: {value}") from exc


def notion_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    token = require_env("NOTION_TOKEN")
    url = "https://api.notion.com/v1" + path
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PaperWorkerError(f"Notion API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise PaperWorkerError(f"Notion API request failed: {exc}") from exc


def github_request(path: str) -> Any:
    token = os.environ.get("GITHUB_TOKEN")
    url = "https://api.github.com" + path
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "paper-worker/0.1")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PaperWorkerError(f"GitHub API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise PaperWorkerError(f"GitHub API request failed: {exc}") from exc


def query_database(
    filter_payload: dict[str, Any] | None = None,
    page_size: int = 50,
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    database_id = require_env("NOTION_PAPER_DATABASE_ID")
    if max_results is not None and max_results <= 0:
        return []

    capped_page_size = min(max(page_size, 1), 100)
    payload: dict[str, Any] = {
        "page_size": capped_page_size if max_results is None else min(capped_page_size, max_results)
    }
    if filter_payload:
        payload["filter"] = filter_payload

    pages: list[dict[str, Any]] = []
    while True:
        data = notion_request("POST", f"/databases/{database_id}/query", payload)
        pages.extend(data.get("results", []))
        if max_results is not None and len(pages) >= max_results:
            return pages[:max_results]
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
        if max_results is not None:
            payload["page_size"] = min(capped_page_size, max_results - len(pages))
    return pages


def database_property_types() -> dict[str, str]:
    global DATABASE_PROPERTY_TYPES
    if DATABASE_PROPERTY_TYPES is not None:
        return DATABASE_PROPERTY_TYPES
    database_id = require_env("NOTION_PAPER_DATABASE_ID")
    data = notion_request("GET", f"/databases/{database_id}")
    properties = data.get("properties", {})
    DATABASE_PROPERTY_TYPES = {
        name: str(prop.get("type") or "")
        for name, prop in properties.items()
        if isinstance(prop, dict)
    }
    return DATABASE_PROPERTY_TYPES


def database_property_type(name: str, default: str = "select") -> str:
    return database_property_types().get(name) or default


def normalize_github_issue_url(value: str) -> str:
    stripped = (value or "").strip().rstrip("/")
    parsed = urllib.parse.urlparse(stripped)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    parts = [part for part in parsed.path.split("/") if part]
    if host == "github.com" and len(parts) >= 4 and parts[2].lower() == "issues":
        return f"https://github.com/{parts[0].lower()}/{parts[1].lower()}/issues/{parts[3]}"
    return stripped


def github_issue_url(repo: str, issue_number: int) -> str:
    return normalize_github_issue_url(f"https://github.com/{repo}/issues/{issue_number}")


def repo_from_github_issue_url(value: str) -> str:
    parsed = urllib.parse.urlparse(normalize_github_issue_url(value))
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc.lower() != "github.com" or len(parts) < 4 or parts[2] != "issues":
        return ""
    return f"{parts[0]}/{parts[1]}"


def notion_issue_indexes() -> tuple[dict[str, list[dict[str, Any]]], dict[int, list[dict[str, Any]]]]:
    pages = query_database(page_size=100)
    by_url: dict[str, list[dict[str, Any]]] = {}
    by_number: dict[int, list[dict[str, Any]]] = {}
    for page in pages:
        issue_url = normalize_github_issue_url(get_text(page, "GitHub Issue URL"))
        if issue_url:
            by_url.setdefault(issue_url, []).append(page)
        value = get_number(page, "GitHub Issue Number")
        if isinstance(value, (int, float)):
            by_number.setdefault(int(value), []).append(page)
    return by_url, by_number


def resolve_notion_issue_page(
    indexes: tuple[dict[str, list[dict[str, Any]]], dict[int, list[dict[str, Any]]]],
    repo: str,
    issue_number: int,
    issue_url: str = "",
) -> tuple[dict[str, Any] | None, str]:
    by_url, by_number = indexes
    candidate_urls = [issue_url, github_issue_url(repo, issue_number)]
    seen_urls: set[str] = set()
    for candidate_url in candidate_urls:
        normalized = normalize_github_issue_url(candidate_url)
        if not normalized or normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        matches = by_url.get(normalized, [])
        if len(matches) == 1:
            return matches[0], "url"
        if len(matches) > 1:
            return None, "duplicate_url"

    candidates = by_number.get(issue_number, [])
    repo_matches = []
    if repo:
        repo_matches = [
            page
            for page in candidates
            if repo_from_github_issue_url(get_text(page, "GitHub Issue URL")) == repo.lower()
        ]
    if len(repo_matches) == 1:
        return repo_matches[0], "repo_url"
    if candidates:
        return None, "ambiguous_number"
    return None, "missing"


def find_page_by_issue(repo: str, issue_number: int, issue_url: str = "") -> dict[str, Any] | None:
    page, _ = resolve_notion_issue_page(notion_issue_indexes(), repo, issue_number, issue_url)
    return page


def rich_text(value: str) -> dict[str, Any]:
    if not value:
        return {"rich_text": []}
    return {"rich_text": [{"type": "text", "text": {"content": value[:2000]}}]}


def select(name: str) -> dict[str, Any]:
    return {"select": {"name": name}}


def status_choice(name: str) -> dict[str, Any]:
    return {"status": {"name": name}}


def page_property_type(page: dict[str, Any], name: str) -> str:
    prop = page.get("properties", {}).get(name, {})
    if isinstance(prop, dict):
        return str(prop.get("type") or "")
    return ""


def status_value(name: str, page: dict[str, Any] | None = None) -> dict[str, Any]:
    prop_type = page_property_type(page, "Status") if page is not None else database_property_type("Status")
    if prop_type == "status":
        return status_choice(name)
    return select(name)


def status_filter(name: str) -> dict[str, Any]:
    prop_type = database_property_type("Status")
    if prop_type == "status":
        return {"property": "Status", "status": {"equals": name}}
    return {"property": "Status", "select": {"equals": name}}


def url_value(value: str) -> dict[str, Any]:
    return {"url": value or None}


def number_value(value: int | float | None) -> dict[str, Any]:
    return {"number": value}


def multi_select(names: list[str]) -> dict[str, Any]:
    return {"multi_select": [{"name": name} for name in names]}


def date_value(value: dt.datetime) -> dict[str, Any]:
    return {"date": {"start": value.replace(microsecond=0).isoformat()}}


def title_value(value: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": value[:2000]}}]}


def get_title(page: dict[str, Any]) -> str:
    prop = page["properties"].get("Title", {})
    parts = prop.get("title", [])
    return "".join(part.get("plain_text", "") for part in parts).strip()


def get_text(page: dict[str, Any], name: str) -> str:
    prop = page["properties"].get(name, {})
    prop_type = prop.get("type")
    if prop_type == "rich_text":
        return "".join(part.get("plain_text", "") for part in prop.get("rich_text", [])).strip()
    if prop_type == "title":
        return "".join(part.get("plain_text", "") for part in prop.get("title", [])).strip()
    if prop_type == "url":
        return prop.get("url") or ""
    if prop_type == "number":
        value = prop.get("number")
        return "" if value is None else str(value)
    if prop_type == "select":
        value = prop.get("select")
        return "" if value is None else value.get("name", "")
    if prop_type == "status":
        value = prop.get("status")
        return "" if value is None else value.get("name", "")
    return ""


def get_number(page: dict[str, Any], name: str) -> int | float | None:
    prop = page["properties"].get(name, {})
    if prop.get("type") != "number":
        return None
    return prop.get("number")


def get_multi_select(page: dict[str, Any], name: str) -> list[str]:
    prop = page["properties"].get(name, {})
    if prop.get("type") != "multi_select":
        return []
    return [item["name"] for item in prop.get("multi_select", [])]


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-._")
    return value[:96] or "paper"


def paper_key(page: dict[str, Any]) -> str:
    explicit = get_text(page, "Paper Key")
    if explicit:
        return explicit
    doi = get_text(page, "DOI")
    if doi:
        return "doi-" + slugify(doi)
    arxiv = get_text(page, "arXiv ID")
    if arxiv:
        return "arxiv-" + slugify(arxiv)
    source_url = get_text(page, "Source URL")
    title = get_title(page)
    seed = source_url or title or page["id"]
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return "paper-" + digest


def page_metadata(page: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "Paper Key",
        "DOI",
        "arXiv ID",
        "Authors",
        "Year",
        "Venue",
        "Source",
        "PDF URL",
        "Source URL",
        "Short Summary JA",
        "Reason",
        "Relevance Note",
        "Priority",
        "Local Folder",
        "Error Message",
    ]
    metadata = {"notion_page_id": page["id"], "title": get_title(page)}
    for field in fields:
        value = get_text(page, field)
        if value:
            metadata[field] = value
    tags = get_multi_select(page, "Tags")
    if tags:
        metadata["Tags"] = tags
    return metadata


def data_root() -> Path:
    return Path(require_env("PAPER_READING_DATA_ROOT")).expanduser().resolve()


def paper_dir_for(page: dict[str, Any]) -> Path:
    return data_root() / "papers" / slugify(paper_key(page))


def update_page(page_id: str, properties: dict[str, Any]) -> None:
    notion_request("PATCH", f"/pages/{page_id}", {"properties": properties})


def create_page(properties: dict[str, Any], content: str = "") -> dict[str, Any]:
    database_id = require_env("NOTION_PAPER_DATABASE_ID")
    payload: dict[str, Any] = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }
    if content:
        payload["children"] = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": content[:2000]}}],
                },
            }
        ]
    return notion_request("POST", "/pages", payload)


def download_pdf(pdf_url: str, destination: Path) -> None:
    req = urllib.request.Request(pdf_url)
    req.add_header("User-Agent", "paper-worker/0.1")
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            content_type = res.headers.get("Content-Type", "")
            data = res.read()
    except urllib.error.URLError as exc:
        raise PaperWorkerError(f"PDF download failed: {exc}") from exc

    if not data:
        raise PaperWorkerError("PDF download returned an empty response")
    if "pdf" not in content_type.lower() and not pdf_url.lower().endswith(".pdf"):
        # Some OA endpoints omit content-type, so this is a warning-level check.
        print(f"warning: response content-type is {content_type!r}", file=sys.stderr)
    destination.write_bytes(data)


def write_initial_files(page: dict[str, Any], paper_dir: Path) -> None:
    paper_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = paper_dir / "metadata.json"
    notes_path = paper_dir / "notes.md"

    metadata = page_metadata(page)
    metadata["paper_key"] = paper_key(page)
    metadata["prepared_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not notes_path.exists():
        title = metadata.get("title") or paper_key(page)
        notes_path.write_text(f"# {title}\n\n## Notes\n\n", encoding="utf-8")


def prepare_page(page: dict[str, Any], dry_run: bool = False, skip_download: bool = False) -> str:
    page_id = page["id"]
    title = get_title(page) or page_id
    target_dir = paper_dir_for(page)
    pdf_url = get_text(page, "PDF URL")

    if dry_run:
        return f"would prepare: {title} -> {target_dir}"

    update_page(
        page_id,
        {
            "Status": status_value("Preparing", page),
            "Local Folder": rich_text(str(target_dir)),
            "Last Processed": date_value(dt.datetime.now(dt.timezone.utc)),
        },
    )

    try:
        write_initial_files(page, target_dir)
        if not pdf_url:
            update_page(
                page_id,
                {
                    "Status": status_value("Ready to read", page),
                    "Local Folder": rich_text(str(target_dir)),
                    "Process Tags": multi_select(["pdf_missing", "needs_manual_check"]),
                    "Error Message": rich_text(""),
                    "Last Processed": date_value(dt.datetime.now(dt.timezone.utc)),
                },
            )
            return f"prepared without PDF: {title} -> {target_dir}"

        pdf_path = target_dir / "paper.pdf"
        if skip_download and not pdf_path.exists():
            update_page(
                page_id,
                {
                    "Status": status_value("Want to read", page),
                    "Local Folder": rich_text(str(target_dir)),
                    "Process Tags": multi_select(["pdf_download_skipped"]),
                    "Error Message": rich_text(""),
                    "Last Processed": date_value(dt.datetime.now(dt.timezone.utc)),
                },
            )
            return f"prepared without downloaded PDF: {title} -> {target_dir}"

        if not skip_download and not pdf_path.exists():
            download_pdf(pdf_url, pdf_path)

        update_page(
            page_id,
            {
                "Status": status_value("Ready to read", page),
                "Local Folder": rich_text(str(target_dir)),
                "Process Tags": multi_select([]),
                "Error Message": rich_text(""),
                "Last Processed": date_value(dt.datetime.now(dt.timezone.utc)),
            },
        )
        return f"prepared: {title} -> {target_dir}"
    except Exception as exc:
        tag = "pdf_missing" if not pdf_url else "pdf_download_failed"
        update_page(
            page_id,
            {
                "Status": status_value("Error", page),
                "Local Folder": rich_text(str(target_dir)),
                "Process Tags": multi_select([tag, "needs_manual_check"]),
                "Error Message": rich_text(str(exc)),
                "Last Processed": date_value(dt.datetime.now(dt.timezone.utc)),
            },
        )
        raise


def command_prepare(args: argparse.Namespace) -> int:
    pages = query_database(
        status_filter("Want to read"),
        page_size=min(args.limit, 100),
        max_results=args.limit,
    )
    if not pages:
        print("No papers with Status = Want to read.")
        return 0
    failures = 0
    for page in pages[: args.limit]:
        try:
            print(prepare_page(page, dry_run=args.dry_run, skip_download=args.skip_download))
        except Exception as exc:
            print(f"failed: {get_title(page) or page['id']}: {exc}", file=sys.stderr)
            failures += 1
            if not args.keep_going:
                return 1
    return 1 if failures else 0


def command_status(args: argparse.Namespace) -> int:
    page_size = 100 if args.limit is None else min(args.limit, 100)
    pages = query_database(page_size=page_size, max_results=args.limit)
    if not pages:
        print("No papers found.")
        return 0
    counts: dict[str, int] = {}
    for page in pages:
        status = get_text(page, "Status") or "(empty)"
        counts[status] = counts.get(status, 0) + 1
    for status in sorted(counts):
        print(f"{status}: {counts[status]}")
    return 0


FIELD_RE = re.compile(r"^- \*\*(?P<key>[^:*]+)(?:[^*]*)?:\*\* (?P<value>.*)$")


def parse_issue_body(body: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    lines = body.splitlines()
    english_title = ""
    summary_lines: list[str] = []
    in_summary = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and not english_title and stripped != "## 概要":
            english_title = stripped[3:].strip()
            continue
        if stripped == "## 概要":
            in_summary = True
            continue
        if in_summary:
            if stripped.startswith(">") or stripped == "---" or stripped.startswith("## "):
                in_summary = False
            elif stripped:
                summary_lines.append(stripped)

        match = FIELD_RE.match(stripped)
        if match:
            key = match.group("key").strip()
            value = match.group("value").strip()
            meta[key] = value

    if english_title:
        meta["English Title"] = english_title
    if summary_lines:
        meta["Summary JA"] = "\n".join(summary_lines).strip()
    return meta


def first_url(value: str) -> str:
    match = re.search(r"https?://\S+", value or "")
    if not match:
        return ""
    url = match.group(0)
    if match.start() > 0 and value[match.start() - 1] == "<" and ">" in url:
        return url.split(">", 1)[0]
    return url.rstrip(").,")


def normalize_year(value: str) -> int | None:
    match = re.search(r"\d{4}", value or "")
    return int(match.group(0)) if match else None


def extract_doi(*values: str) -> str:
    joined = " ".join(v or "" for v in values)
    match = re.search(r"10\.\d{4,9}/[^\s)]+", joined, flags=re.I)
    return match.group(0).rstrip(".,") if match else ""


def extract_arxiv(*values: str) -> str:
    joined = " ".join(v or "" for v in values)
    modern_id = r"\d{4}\.\d{4,5}"
    legacy_archive = (
        r"astro-ph|cond-mat|gr-qc|hep-ex|hep-lat|hep-ph|hep-th|math-ph|nlin|"
        r"nucl-ex|nucl-th|physics|quant-ph|cs|math|q-bio|q-fin|stat"
    )
    legacy_id = rf"(?:{legacy_archive})(?:\.[A-Za-z-]+)?/\d{{7}}"

    match = re.search(rf"arxiv\.org/(?:abs|pdf)/({modern_id}|{legacy_id})(?:v\d+)?", joined, flags=re.I)
    if match:
        return match.group(1)
    match = re.search(rf"\b({modern_id})(?:v\d+)?\b", joined)
    if match:
        return match.group(1)
    match = re.search(rf"(?<![/\w.-])({legacy_id})(?:v\d+)?\b", joined, flags=re.I)
    return match.group(1) if match else ""


def pdf_url_from(source_url: str, oa_url: str) -> str:
    for url in [oa_url, source_url]:
        if not url or url == "N/A":
            continue
        lower = url.lower()
        if lower.endswith(".pdf") or "/pdf" in lower or "arxiv.org/pdf/" in lower:
            return url
    return ""


def paper_key_from_issue(repo: str, issue: dict[str, Any], meta: dict[str, Any]) -> str:
    source_url = first_url(meta.get("Source URL", ""))
    oa_url = first_url(meta.get("OA URL", ""))
    doi = extract_doi(source_url, oa_url)
    arxiv = extract_arxiv(source_url, oa_url)
    if doi:
        return "doi-" + slugify(doi)
    if arxiv:
        return "arxiv-" + slugify(arxiv)
    return f"github-{slugify(repo)}-issue-{issue['number']}"


def issue_to_properties(repo: str, issue: dict[str, Any]) -> dict[str, Any]:
    body = issue.get("body") or ""
    meta = parse_issue_body(body)
    source_url = first_url(meta.get("Source URL", ""))
    oa_url = first_url(meta.get("OA URL", ""))
    labels = [label["name"] for label in issue.get("labels", [])]
    year = normalize_year(meta.get("Year", ""))
    doi = extract_doi(source_url, oa_url)
    arxiv = extract_arxiv(source_url, oa_url)
    status = "Read" if issue.get("state") == "closed" else "Inbox"
    oa_status = meta.get("OA Status", "") or "unknown"
    if oa_status not in {"gold", "green", "bronze", "hybrid", "closed"}:
        oa_status = "unknown"

    properties: dict[str, Any] = {
        "Title": title_value(issue.get("title") or meta.get("English Title") or f"Issue {issue['number']}"),
        "Status": status_value(status),
        "GitHub Issue Number": number_value(issue["number"]),
        "GitHub Issue URL": url_value(issue.get("html_url", "")),
        "Original Issue State": select((issue.get("state") or "").upper()),
        "Paper Key": rich_text(paper_key_from_issue(repo, issue, meta)),
        "Authors": rich_text(meta.get("Authors", "")),
        "Venue": rich_text(meta.get("Venue", "")),
        "Source": rich_text(meta.get("Label", "github-issues")),
        "Source URL": url_value(source_url),
        "PDF URL": url_value(pdf_url_from(source_url, oa_url)),
        "Short Summary JA": rich_text(meta.get("Summary JA", "")),
        "Reason": rich_text(f"Imported from GitHub issue {repo}#{issue['number']}"),
        "Tags": multi_select(labels[:20]),
        "OA Status": select(oa_status),
    }
    if year is not None:
        properties["Year"] = number_value(year)
    if doi:
        properties["DOI"] = rich_text(doi)
    if arxiv:
        properties["arXiv ID"] = rich_text(arxiv)
    return properties


def github_issues(repo: str, limit: int) -> list[dict[str, Any]]:
    encoded_repo = urllib.parse.quote(repo, safe="/")
    issues: list[dict[str, Any]] = []
    page = 1
    while len(issues) < limit:
        batch = github_request(f"/repos/{encoded_repo}/issues?state=all&per_page=100&page={page}")
        if not batch:
            break
        for issue in batch:
            if "pull_request" in issue:
                continue
            issues.append(issue)
            if len(issues) >= limit:
                break
        page += 1
    return issues


def command_import_github_issues(args: argparse.Namespace) -> int:
    repo = args.repo or env_or_default("GITHUB_REPOSITORY", "tomiokario/my-paper-reading-list")
    issues = github_issues(repo, args.limit)
    indexes = notion_issue_indexes()
    created = 0
    skipped = 0
    backfilled = 0
    ambiguous = 0
    for issue in issues:
        issue_url = normalize_github_issue_url(issue.get("html_url", "") or github_issue_url(repo, issue["number"]))
        page, match_reason = resolve_notion_issue_page(indexes, repo, issue["number"], issue_url)
        if page:
            skipped += 1
            continue
        if match_reason in {"ambiguous_number", "duplicate_url"}:
            print(
                f"skipped ambiguous issue #{issue['number']} from {repo} ({match_reason}); check duplicate or missing GitHub Issue URL fields",
                file=sys.stderr,
            )
            ambiguous += 1
            skipped += 1
            continue
        properties = issue_to_properties(repo, issue)
        if args.dry_run:
            print(f"would import #{issue['number']}: {issue['title']}")
            created += 1
            continue
        create_page(properties)
        print(f"imported #{issue['number']}: {issue['title']}")
        created += 1
    action = "would_import" if args.dry_run else "imported"
    print(f"done: {action}={created} skipped={skipped} backfilled={backfilled} ambiguous={ambiguous}")
    return 0


def issue_number_from_project_item(item: dict[str, Any]) -> int | None:
    content = item.get("content")
    if not isinstance(content, dict):
        return None
    number = content.get("number")
    return number if isinstance(number, int) else None


def project_item_issue_url(item: dict[str, Any]) -> str:
    content = item.get("content")
    if isinstance(content, dict):
        url = normalize_github_issue_url(str(content.get("url") or ""))
        if url:
            return url
        repository = str(content.get("repository") or "")
        number = issue_number_from_project_item(item)
        if repository and number is not None:
            return github_issue_url(repository, number)

    repository_url = str(item.get("repository") or "")
    repo = ""
    if repository_url:
        parsed = urllib.parse.urlparse(repository_url)
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.netloc.lower() == "github.com" and len(parts) >= 2:
            repo = f"{parts[0]}/{parts[1]}"
    number = issue_number_from_project_item(item)
    return github_issue_url(repo, number) if repo and number is not None else ""


def project_item_title(item: dict[str, Any]) -> str:
    content = item.get("content")
    if isinstance(content, dict) and content.get("title"):
        return str(content["title"])
    if item.get("title"):
        return str(item["title"])
    number = issue_number_from_project_item(item)
    return f"issue #{number}" if number is not None else "project item"


def notion_pages_by_issue_url() -> dict[str, dict[str, Any]]:
    by_url, _ = notion_issue_indexes()
    return {issue_url: pages[0] for issue_url, pages in by_url.items() if len(pages) == 1}


def github_project_items(owner: str, project_number: int, limit: int) -> list[dict[str, Any]]:
    command = [
        "gh",
        "project",
        "item-list",
        str(project_number),
        "--owner",
        owner,
        "--limit",
        str(limit),
        "--format",
        "json",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, encoding="utf-8")
    except FileNotFoundError as exc:
        raise PaperWorkerError("GitHub CLI is not installed or not on PATH") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        if "project" in detail.lower():
            detail += "\nRun: gh auth refresh -s project"
        raise PaperWorkerError(f"GitHub Project item-list failed: {detail}")

    data = json.loads(completed.stdout)
    items = data.get("items", data if isinstance(data, list) else [])
    if not isinstance(items, list):
        raise PaperWorkerError("Unexpected GitHub Project item-list response")
    return [item for item in items if isinstance(item, dict)]


def project_item_update_properties(
    item: dict[str, Any],
    page: dict[str, Any],
    force_status: bool,
) -> dict[str, Any]:
    properties: dict[str, Any] = {}

    project_status = str(item.get("status") or "").strip()
    target_status = PROJECT_STATUS_MAP.get(project_status.lower())
    current_status = get_text(page, "Status")
    if target_status and target_status != current_status:
        should_preserve = (
            not force_status
            and current_status in LOCAL_WORK_STATUSES
            and target_status in DEMOTING_PROJECT_TARGETS
        )
        if not should_preserve:
            properties["Status"] = status_value(target_status, page)

    project_priority = str(item.get("priority") or "").strip()
    target_priority = PROJECT_PRIORITY_MAP.get(project_priority)
    current_priority = get_text(page, "Priority")
    if target_priority and target_priority != current_priority:
        properties["Priority"] = select(target_priority)

    return properties


def command_sync_github_project(args: argparse.Namespace) -> int:
    owner = args.owner or env_or_default("GITHUB_PROJECT_OWNER", "tomiokario")
    project_number = args.project_number or env_int_or_default("GITHUB_PROJECT_NUMBER", 2)
    items = github_project_items(owner, project_number, args.limit)
    indexes = notion_issue_indexes()
    updated = 0
    skipped = 0
    missing = 0
    ambiguous = 0

    for item in items:
        issue_number = issue_number_from_project_item(item)
        if issue_number is None:
            skipped += 1
            continue

        issue_url = project_item_issue_url(item)
        repo = repo_from_github_issue_url(issue_url)
        page, match_reason = resolve_notion_issue_page(indexes, repo, issue_number, issue_url)
        if not page:
            if match_reason in {"ambiguous_number", "duplicate_url"}:
                ambiguous += 1
                print(
                    f"ambiguous Notion card for issue #{issue_number} ({issue_url}, {match_reason}): {project_item_title(item)}",
                    file=sys.stderr,
                )
                skipped += 1
                continue
            missing += 1
            print(f"missing Notion card for issue #{issue_number} ({issue_url}): {project_item_title(item)}")
            continue

        properties = project_item_update_properties(item, page, args.force_status)
        if not properties:
            skipped += 1
            continue

        property_names = ", ".join(sorted(properties))
        if args.dry_run:
            print(f"would update issue #{issue_number}: {property_names}")
        else:
            update_page(page["id"], properties)
            print(f"updated issue #{issue_number}: {property_names}")
        updated += 1

    action = "would_update" if args.dry_run else "updated"
    print(f"done: {action}={updated} skipped={skipped} missing={missing} ambiguous={ambiguous}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Paper reading workflow helper")
    parser.add_argument("--env-file", default=".env", help="Path to a local env file")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Show Notion status counts")
    status.add_argument("--limit", type=int, default=None, help="Limit rows for debugging; default scans all")
    status.set_defaults(func=command_status)

    prepare = subparsers.add_parser("prepare", help="Prepare papers marked Want to read")
    prepare.add_argument("--limit", type=int, default=10)
    prepare.add_argument("--dry-run", action="store_true")
    prepare.add_argument("--skip-download", action="store_true")
    prepare.add_argument("--keep-going", action="store_true")
    prepare.set_defaults(func=command_prepare)

    import_issues = subparsers.add_parser("import-github-issues", help="Import GitHub issues into Notion")
    import_issues.add_argument("--repo", default=None)
    import_issues.add_argument("--limit", type=int, default=200)
    import_issues.add_argument("--dry-run", action="store_true")
    import_issues.set_defaults(func=command_import_github_issues)

    sync_project = subparsers.add_parser(
        "sync-github-project",
        help="Sync GitHub Projects status and priority into Notion",
    )
    sync_project.add_argument("--owner", default=None)
    sync_project.add_argument(
        "--project-number",
        type=int,
        default=None,
    )
    sync_project.add_argument("--limit", type=int, default=200)
    sync_project.add_argument("--dry-run", action="store_true")
    sync_project.add_argument(
        "--force-status",
        action="store_true",
        help="Overwrite local work statuses such as Ready to read when a project status maps backwards",
    )
    sync_project.set_defaults(func=command_sync_github_project)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    load_dotenv(Path(args.env_file))
    try:
        return args.func(args)
    except PaperWorkerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
