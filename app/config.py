from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # When true, GitHub/Slack calls are logged instead of hitting real APIs.
    # The agent's reasoning (OpenAI calls) always runs for real — this only
    # mocks the side-effecting integrations, so the eval harness can run
    # without an approval workflow attached to a live repo.
    mock_mode: bool = True

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    github_token: str = ""
    github_webhook_secret: str = ""
    github_repo: str = ""  # "owner/name"

    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_approval_channel: str = "#agent-approvals"

    database_url: str = "sqlite:///./triage_agent.db"

    agent_max_steps: int = 6
    eval_accuracy_threshold: float = 0.7


@lru_cache
def get_settings() -> Settings:
    return Settings()
