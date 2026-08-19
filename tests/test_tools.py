import pytest

from app.agent import tools
from app.agent.tools import RiskTier
from app.config import get_settings


@pytest.fixture(autouse=True)
def force_mock_mode(monkeypatch):
    # get_settings() is lru_cached, so every module holds the same instance —
    # mutating it here forces mock behavior regardless of the local .env,
    # which may have MOCK_MODE=false and a real token set for manual testing.
    monkeypatch.setattr(get_settings(), "mock_mode", True)


def test_risk_tiers():
    assert tools.risk_of("search_related_issues") == RiskTier.READ_ONLY
    assert tools.risk_of("label_issue") == RiskTier.LOW
    assert tools.risk_of("post_comment") == RiskTier.LOW
    assert tools.risk_of("assign_issue") == RiskTier.HIGH
    assert tools.risk_of("page_oncall") == RiskTier.HIGH


def test_mock_execution_does_not_raise():
    result = tools.execute("label_issue", repo="octocat/hello-world", issue_number=1, label="bug")
    assert "mock" in result


def test_tool_schemas_have_required_fields():
    for schema in tools.tool_schemas():
        fn = schema["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
