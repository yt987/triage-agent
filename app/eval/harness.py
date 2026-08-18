"""Offline evaluation harness for the triage agent.

Runs the agent against a labeled dataset of issues and checks whether it applied
the expected label. GitHub/Slack side effects are mocked (MOCK_MODE=true) so this
never touches a real repo, but the agent's actual reasoning still calls OpenAI —
that's the thing being scored. Intended to run as a CI gate: a prompt or tool
change that drops accuracy below the threshold fails the build.
"""

import json
import sys
from pathlib import Path
from typing import Optional

from app.agent.loop import run_agent
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.models import AgentRun, Issue, ToolCallLog

DATASET_PATH = Path(__file__).parent / "dataset.jsonl"


def load_dataset() -> list[dict]:
    with open(DATASET_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def applied_label(db, run_id: int) -> Optional[str]:
    calls = db.query(ToolCallLog).filter_by(run_id=run_id, tool_name="label_issue").all()
    if not calls:
        return None
    return json.loads(calls[-1].arguments).get("label")


def main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        print(
            "OPENAI_API_KEY is required to run the eval harness — the agent's "
            "reasoning calls the real model even when MOCK_MODE hides GitHub/Slack.",
            file=sys.stderr,
        )
        sys.exit(1)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    dataset = load_dataset()

    correct = 0
    for i, case in enumerate(dataset):
        issue = Issue(repo="eval/repo", number=i, title=case["title"], body=case.get("body", ""))
        db.add(issue)
        db.flush()
        run = AgentRun(issue_id=issue.id)
        db.add(run)
        db.flush()

        run_agent(db, run, "eval/repo", i, case["title"], case.get("body", ""))
        label = applied_label(db, run.id)
        is_correct = label == case["expected_label"]
        correct += is_correct
        print(f"[{'OK' if is_correct else 'MISS'}] #{i} expected={case['expected_label']} got={label}")

    accuracy = correct / len(dataset)
    print(f"\nAccuracy: {accuracy:.2%} ({correct}/{len(dataset)}) threshold={settings.eval_accuracy_threshold:.0%}")
    db.close()

    if accuracy < settings.eval_accuracy_threshold:
        sys.exit(1)


if __name__ == "__main__":
    main()
