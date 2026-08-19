import json
import logging

from openai import OpenAI
from sqlalchemy.orm import Session

from app.agent import tools
from app.agent.tools import RiskTier
from app.config import get_settings
from app.integrations import slack_client
from app.models import AgentRun, Approval, ApprovalStatus, ToolCallLog

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are a triage agent for a software repository's issue tracker.

Given a new issue, decide how to triage it:
1. Optionally search for related past issues to inform your decision.
2. Apply exactly one label from the allowed set.
3. Either post a comment (e.g. asking for repro steps) or, only for genuinely
   critical/urgent issues, page the on-call engineer.

Only call the tools that are necessary, then stop. Do not repeat an action you've
already taken in this conversation."""


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def run_agent(db: Session, run: AgentRun, repo: str, issue_number: int, title: str, body: str) -> str:
    client = _client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Repo: {repo}\nIssue #{issue_number}: {title}\n\n{body}",
        },
    ]

    for step in range(settings.agent_max_steps):
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            tools=tools.tool_schemas(),
        )
        message = response.choices[0].message
        if response.usage:
            run.prompt_tokens += response.usage.prompt_tokens
            run.completion_tokens += response.usage.completion_tokens

        if not message.tool_calls:
            run.outcome = message.content or "no action taken"
            run.steps_taken = step + 1
            db.commit()
            return run.outcome

        messages.append(message.model_dump(exclude_none=True))

        for call in message.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments or "{}")
            risk = tools.risk_of(name)

            log = ToolCallLog(
                run_id=run.id,
                step=step,
                tool_name=name,
                arguments=json.dumps(args),
                risk_tier=risk.value,
            )

            if risk == RiskTier.HIGH:
                approval = Approval(
                    run_id=run.id,
                    tool_name=name,
                    arguments=json.dumps(args),
                    status=ApprovalStatus.PENDING,
                )
                db.add(approval)
                db.flush()
                slack_client.post_approval_request(approval.id, name, args)
                result = f"queued for human approval (approval_id={approval.id})"
            else:
                try:
                    result = tools.execute(name, **args)
                except Exception as exc:
                    logger.warning("tool %s failed: %s", name, exc)
                    result = f"error: {exc}"

            log.result = result
            db.add(log)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

        db.commit()

    run.outcome = "max steps reached without resolution"
    run.steps_taken = settings.agent_max_steps
    db.commit()
    return run.outcome
