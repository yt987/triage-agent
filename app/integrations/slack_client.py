import hashlib
import hmac
import json
import time

import httpx

from app.config import get_settings

settings = get_settings()


def _mock(action: str, **kwargs) -> str:
    return f"[mock] {action}({json.dumps(kwargs)})"


def post_approval_request(approval_id: int, tool_name: str, arguments: dict) -> str:
    if settings.mock_mode or not settings.slack_bot_token:
        return _mock("post_approval_request", approval_id=approval_id, tool_name=tool_name, arguments=arguments)

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Approval needed*: `{tool_name}` with `{json.dumps(arguments)}`",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "action_id": "approve",
                    "value": str(approval_id),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Deny"},
                    "style": "danger",
                    "action_id": "deny",
                    "value": str(approval_id),
                },
            ],
        },
    ]
    resp = httpx.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
        json={"channel": settings.slack_approval_channel, "blocks": blocks},
        timeout=10,
    )
    resp.raise_for_status()
    return "posted approval request"


def post_approval_resolution(tool_name: str, status: str, result: str) -> str:
    if settings.mock_mode or not settings.slack_bot_token:
        return _mock("post_approval_resolution", tool_name=tool_name, status=status, result=result)
    text = f"`{tool_name}` was *{status}* — {result}"
    resp = httpx.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
        json={"channel": settings.slack_approval_channel, "text": text},
        timeout=10,
    )
    resp.raise_for_status()
    return "posted resolution"


def page_oncall(reason: str) -> str:
    if settings.mock_mode or not settings.slack_bot_token:
        return _mock("page_oncall", reason=reason)
    resp = httpx.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
        json={"channel": settings.slack_approval_channel, "text": f":rotating_light: Paging on-call: {reason}"},
        timeout=10,
    )
    resp.raise_for_status()
    return "paged on-call"


def verify_signature(body: bytes, timestamp: str, signature: str) -> bool:
    if not settings.slack_signing_secret:
        return True  # dev/mock mode — no secret configured yet
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False
    basestring = f"v0:{timestamp}:{body.decode()}"
    computed = "v0=" + hmac.new(
        settings.slack_signing_secret.encode(), basestring.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)
