from app.agent import tools
from app.agent.tools import RiskTier


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
