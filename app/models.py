import datetime as dt
import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db import Base


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True)
    repo = Column(String, nullable=False)
    number = Column(Integer, nullable=False)
    title = Column(Text, nullable=False)
    body = Column(Text, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    runs = relationship("AgentRun", back_populates="issue")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, ForeignKey("issues.id"))
    started_at = Column(DateTime, default=dt.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    steps_taken = Column(Integer, default=0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    outcome = Column(Text, default="")

    issue = relationship("Issue", back_populates="runs")
    tool_calls = relationship("ToolCallLog", back_populates="run")


class ToolCallLog(Base):
    __tablename__ = "tool_calls"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id"))
    step = Column(Integer)
    tool_name = Column(String)
    arguments = Column(Text)
    risk_tier = Column(String)
    result = Column(Text, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    run = relationship("AgentRun", back_populates="tool_calls")


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id"))
    tool_name = Column(String)
    arguments = Column(Text)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
