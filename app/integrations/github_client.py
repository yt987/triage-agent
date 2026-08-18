import json

import httpx

from app.config import get_settings

settings = get_settings()

API_ROOT = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
    }


def _mock(action: str, **kwargs) -> str:
    return f"[mock] {action}({json.dumps(kwargs)})"


def search_related_issues(query: str, repo: str) -> str:
    if settings.mock_mode or not settings.github_token:
        return _mock("search_related_issues", query=query, repo=repo)
    resp = httpx.get(
        f"{API_ROOT}/search/issues",
        params={"q": f"repo:{repo} {query} in:title,body"},
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])[:5]
    return json.dumps([{"number": i["number"], "title": i["title"]} for i in items])


def add_label(repo: str, issue_number: int, label: str) -> str:
    if settings.mock_mode or not settings.github_token:
        return _mock("add_label", repo=repo, issue_number=issue_number, label=label)
    resp = httpx.post(
        f"{API_ROOT}/repos/{repo}/issues/{issue_number}/labels",
        json={"labels": [label]},
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return f"labeled #{issue_number} with {label}"


def post_comment(repo: str, issue_number: int, body: str) -> str:
    if settings.mock_mode or not settings.github_token:
        return _mock("post_comment", repo=repo, issue_number=issue_number, body=body)
    resp = httpx.post(
        f"{API_ROOT}/repos/{repo}/issues/{issue_number}/comments",
        json={"body": body},
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return f"commented on #{issue_number}"


def assign(repo: str, issue_number: int, assignee: str) -> str:
    if settings.mock_mode or not settings.github_token:
        return _mock("assign", repo=repo, issue_number=issue_number, assignee=assignee)
    resp = httpx.post(
        f"{API_ROOT}/repos/{repo}/issues/{issue_number}/assignees",
        json={"assignees": [assignee]},
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return f"assigned #{issue_number} to {assignee}"
