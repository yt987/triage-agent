import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qs

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.agent import tools
from app.agent.loop import run_agent
from app.config import get_settings
from app.db import Base, SessionLocal, engine, get_db
from app.integrations import slack_client
from app.models import AgentRun, Approval, ApprovalStatus, Issue

logging.basicConfig(level=logging.INFO)
settings = get_settings()

app = FastAPI(title="Triage Agent")

Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok", "mock_mode": settings.mock_mode}


def _verify_github_signature(body: bytes, signature: Optional[str]):
    if not settings.github_webhook_secret:
        return  # dev/mock mode — no secret configured yet
    if not signature:
        raise HTTPException(status_code=401, detail="missing signature")
    digest = "sha256=" + hmac.new(settings.github_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, signature):
        raise HTTPException(status_code=401, detail="bad signature")


def _process_issue(repo: str, issue_number: int, title: str, body: str):
    """Runs in a background task, so it opens its own DB session rather than
    reusing the request-scoped one (which may already be closed by the time
    this executes)."""
    db = SessionLocal()
    try:
        issue = Issue(repo=repo, number=issue_number, title=title, body=body)
        db.add(issue)
        db.flush()

        run = AgentRun(issue_id=issue.id)
        db.add(run)
        db.flush()

        run_agent(db, run, repo, issue_number, title, body)
    finally:
        db.close()


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(default=None),
    x_github_event: Optional[str] = Header(default=None),
):
    raw = await request.body()
    _verify_github_signature(raw, x_hub_signature_256)

    if x_github_event != "issues":
        return {"status": "ignored", "event": x_github_event}

    payload = json.loads(raw)
    if payload.get("action") not in ("opened", "reopened"):
        return {"status": "ignored", "action": payload.get("action")}

    issue = payload["issue"]
    repo = payload["repository"]["full_name"]

    background_tasks.add_task(
        _process_issue, repo, issue["number"], issue["title"], issue.get("body") or ""
    )
    return {"status": "accepted"}


@app.post("/approvals/{approval_id}/approve")
def approve(approval_id: int, db: Session = Depends(get_db)):
    return _resolve_approval(approval_id, ApprovalStatus.APPROVED, db)


@app.post("/approvals/{approval_id}/deny")
def deny(approval_id: int, db: Session = Depends(get_db)):
    return _resolve_approval(approval_id, ApprovalStatus.DENIED, db)


@app.post("/slack/interactivity")
async def slack_interactivity(
    request: Request,
    x_slack_signature: Optional[str] = Header(default=None),
    x_slack_request_timestamp: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    raw = await request.body()
    if not slack_client.verify_signature(raw, x_slack_request_timestamp or "0", x_slack_signature or ""):
        raise HTTPException(status_code=401, detail="bad slack signature")

    form = parse_qs(raw.decode())
    payload = json.loads(form["payload"][0])
    action = payload["actions"][0]
    approval_id = int(action["value"])
    status = ApprovalStatus.APPROVED if action["action_id"] == "approve" else ApprovalStatus.DENIED

    resolution = _resolve_approval(approval_id, status, db)
    approval = db.get(Approval, approval_id)
    slack_client.post_approval_resolution(approval.tool_name, resolution["status"], resolution["result"])
    return {"status": "ok"}


def _resolve_approval(approval_id: int, status: ApprovalStatus, db: Session):
    approval = db.get(Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="approval not found")
    if approval.status != ApprovalStatus.PENDING:
        return {"status": approval.status.value, "note": "already resolved"}

    approval.status = status
    approval.resolved_at = datetime.utcnow()

    result = "denied by reviewer"
    if status == ApprovalStatus.APPROVED:
        args = json.loads(approval.arguments)
        result = tools.execute(approval.tool_name, **args)

    db.commit()
    return {"status": approval.status.value, "result": result}
