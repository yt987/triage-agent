from enum import Enum
from typing import Any

from app.integrations import github_client, slack_client


class RiskTier(str, Enum):
    READ_ONLY = "read_only"
    LOW = "low"    # reversible, small blast radius — auto-executes
    HIGH = "high"  # requires human approval before executing


def _search_related_issues(query: str, repo: str) -> str:
    return github_client.search_related_issues(query, repo)


def _label_issue(repo: str, issue_number: int, label: str) -> str:
    return github_client.add_label(repo, issue_number, label)


def _post_comment(repo: str, issue_number: int, body: str) -> str:
    return github_client.post_comment(repo, issue_number, body)


def _assign_issue(repo: str, issue_number: int, assignee: str) -> str:
    return github_client.assign(repo, issue_number, assignee)


def _page_oncall(reason: str) -> str:
    return slack_client.page_oncall(reason)


TOOLS: dict[str, dict[str, Any]] = {
    "search_related_issues": {
        "risk": RiskTier.READ_ONLY,
        "fn": _search_related_issues,
        "schema": {
            "type": "function",
            "function": {
                "name": "search_related_issues",
                "description": "Search past issues in the repo for similar reports.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "repo": {"type": "string"},
                    },
                    "required": ["query", "repo"],
                },
            },
        },
    },
    "label_issue": {
        "risk": RiskTier.LOW,
        "fn": _label_issue,
        "schema": {
            "type": "function",
            "function": {
                "name": "label_issue",
                "description": (
                    "Apply exactly one label to a GitHub issue. Allowed labels: "
                    "bug, question, enhancement, documentation, needs-repro."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string"},
                        "issue_number": {"type": "integer"},
                        "label": {
                            "type": "string",
                            "enum": ["bug", "question", "enhancement", "documentation", "needs-repro"],
                        },
                    },
                    "required": ["repo", "issue_number", "label"],
                },
            },
        },
    },
    "post_comment": {
        "risk": RiskTier.LOW,
        "fn": _post_comment,
        "schema": {
            "type": "function",
            "function": {
                "name": "post_comment",
                "description": "Post a comment on the issue, e.g. asking for repro steps or explaining triage.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string"},
                        "issue_number": {"type": "integer"},
                        "body": {"type": "string"},
                    },
                    "required": ["repo", "issue_number", "body"],
                },
            },
        },
    },
    "assign_issue": {
        "risk": RiskTier.HIGH,
        "fn": _assign_issue,
        "schema": {
            "type": "function",
            "function": {
                "name": "assign_issue",
                "description": "Assign the issue to a specific engineer. Requires human approval.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string"},
                        "issue_number": {"type": "integer"},
                        "assignee": {"type": "string"},
                    },
                    "required": ["repo", "issue_number", "assignee"],
                },
            },
        },
    },
    "page_oncall": {
        "risk": RiskTier.HIGH,
        "fn": _page_oncall,
        "schema": {
            "type": "function",
            "function": {
                "name": "page_oncall",
                "description": "Page the on-call engineer for a critical/urgent issue. Requires human approval.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                    },
                    "required": ["reason"],
                },
            },
        },
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [t["schema"] for t in TOOLS.values()]


def risk_of(tool_name: str) -> RiskTier:
    return TOOLS[tool_name]["risk"]


def execute(tool_name: str, **kwargs) -> str:
    return TOOLS[tool_name]["fn"](**kwargs)
