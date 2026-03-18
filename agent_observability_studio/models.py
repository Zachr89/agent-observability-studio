"""Data models for observability platform."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class SessionStatus(str, Enum):
    """Status of an agent session."""

    ACTIVE = "active"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class InteractionType(str, Enum):
    """Type of agent interaction."""

    LLM_CALL = "llm_call"
    TOOL_USE = "tool_use"
    MEMORY_ACCESS = "memory_access"
    AGENT_COMMUNICATION = "agent_communication"


class Session(BaseModel):
    """An agent execution session."""

    id: UUID = Field(default_factory=uuid4)
    agent_name: str
    task_id: Optional[str] = None
    status: SessionStatus = SessionStatus.ACTIVE
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    parent_session_id: Optional[UUID] = None


class Interaction(BaseModel):
    """A single LLM or tool interaction within a session."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    type: InteractionType = InteractionType.LLM_CALL
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request: Dict[str, Any]
    response: Dict[str, Any]
    tokens_used: int
    cost_usd: float = 0.0
    latency_ms: Optional[int] = None
    model: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionCreate(BaseModel):
    """Request to create a new session."""

    agent_name: str
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    parent_session_id: Optional[UUID] = None


class SessionUpdate(BaseModel):
    """Request to update a session."""

    status: Optional[SessionStatus] = None
    end_time: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class InteractionCreate(BaseModel):
    """Request to log an interaction."""

    session_id: UUID
    type: InteractionType = InteractionType.LLM_CALL
    request: Dict[str, Any]
    response: Dict[str, Any]
    tokens_used: int
    cost_usd: float = 0.0
    latency_ms: Optional[int] = None
    model: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionQuery(BaseModel):
    """Query parameters for filtering sessions."""

    agent_name: Optional[str] = None
    task_id: Optional[str] = None
    status: Optional[SessionStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    min_tokens: Optional[int] = None
    max_tokens: Optional[int] = None
    limit: int = 100
    offset: int = 0


class CostBreakdown(BaseModel):
    """Token cost analysis results."""

    total_cost_usd: float
    total_tokens: int
    by_agent: Dict[str, float]
    by_model: Dict[str, float]
    by_task: Dict[str, float]
    time_range: tuple[datetime, datetime]


class DecisionNode(BaseModel):
    """Node in an agent decision tree."""

    session_id: UUID
    agent_name: str
    task_id: Optional[str]
    children: list[UUID] = Field(default_factory=list)
    status: SessionStatus
    total_cost_usd: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
