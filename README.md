# Triage Agent

An autonomous agent that triages incoming GitHub issues: it reads a new issue,
decides how to classify and respond to it, and calls real GitHub/Slack APIs to
act — labeling, commenting, assigning, or paging on-call. Actions are risk-tiered:
low-risk actions (labeling, commenting) execute automatically, while high-risk
actions (assigning, paging) are routed through a Slack approval before they run.

Built to demonstrate agentic tool-use integrated with real external systems,
not just an LLM wrapper — the parts that usually separate a demo from something
you'd trust in production: guardrails on autonomous actions, an evaluation
harness that gates deploys, and a deployable service instead of a notebook.

## Architecture

```
GitHub issue opened
      |
      v
POST /webhook/github  (HMAC-verified)
      |
      v
Agent loop (OpenAI function-calling, ReAct-style, max-step budget)
      |
      +-- read-only / low-risk tool  -> executes immediately
      |       (search_related_issues, label_issue, post_comment)
      |
      +-- high-risk tool  -> Approval row created, Slack message posted
              (assign_issue, page_oncall)                |
                                                            v
                                          POST /approvals/{id}/approve|deny
                                                            |
                                                            v
                                                  tool executes, run logged
```

Every step (thought → tool call → result) is logged to the database
(`agent_runs`, `tool_calls`, `approvals`) for later inspection.

## Stack

FastAPI · SQLAlchemy (SQLite locally, Postgres via Docker Compose) · OpenAI
function-calling · GitHub REST API · Slack Web API · Docker · GitHub Actions

## Mock mode

`MOCK_MODE=true` (the default) mocks only the **side-effecting integrations**
(GitHub writes, Slack messages) — the agent's reasoning still calls the real
OpenAI API. This lets you run the full loop and the eval harness without a
live repo or Slack workspace, and without risking a stray label/assignment
hitting a real issue while you're developing prompts.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY at minimum
uvicorn app.main:app --reload
```

Then simulate a webhook:

```bash
curl -X POST localhost:8000/webhook/github \
  -H "X-GitHub-Event: issues" \
  -H "Content-Type: application/json" \
  -d '{"action":"opened","repository":{"full_name":"octocat/hello-world"},
       "issue":{"number":1,"title":"App crashes on launch","body":"NPE on startup, v2.3"}}'
```

Check `agent_runs` / `tool_calls` in `triage_agent.db` (or hit a small
inspection endpoint you add later) to see what the agent decided.

## Evaluation

```bash
python -m app.eval.harness
```

Runs the agent over `app/eval/dataset.jsonl` (10 labeled historical-style
issues) and reports labeling accuracy. `EVAL_ACCURACY_THRESHOLD` (default 0.7)
is the CI gate — the `eval` job in `.github/workflows/ci.yml` fails the build
if accuracy drops below it, so a prompt or tool change that regresses the
agent's judgment can't ship silently. The eval job only runs in CI if an
`OPENAI_API_KEY` repo secret is configured, since it costs API credit.

## Running with Docker

```bash
docker compose up --build
```

Runs the app against a real Postgres instance instead of SQLite.

## Setting up real integrations

- **GitHub**: create a personal access token (repo scope) and a webhook on a
  repo pointing at `POST /webhook/github`; set `GITHUB_TOKEN` and
  `GITHUB_WEBHOOK_SECRET`.
- **Slack**: create a Slack app with `chat:write` scope, install it to a
  workspace, set `SLACK_BOT_TOKEN` and `SLACK_APPROVAL_CHANNEL`. Wire up an
  Interactivity endpoint pointing at your approval buttons if you want the
  Approve/Deny buttons to call `/approvals/{id}/approve|deny` directly instead
  of doing it manually.
- Flip `MOCK_MODE=false` once both are configured.

## Deploying

Container is stateless aside from the DB — push the image to ECR and run it
on Fargate (or EC2) behind an ALB, point the GitHub webhook at the public URL,
and use RDS Postgres instead of the Compose-local one.

## Known simplifications / next steps

- Webhook processing uses FastAPI `BackgroundTasks` for simplicity; a queue
  (SQS/Celery) would be the natural next step under real load.
- `search_related_issues` does a live GitHub search rather than an embedding
  lookup over resolved issues — swapping in a vector store (pgvector) for
  actual semantic memory is a natural extension, and would reuse the
  embedding/hybrid-retrieval work from other projects.
- No auth on `/approvals/*` yet — fine for a portfolio demo, not for
  production (would need to verify the Slack interactivity signature end to
  end rather than just exposing plain REST endpoints).
