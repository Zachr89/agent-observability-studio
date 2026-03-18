"""Python SDK for instrumenting agents."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
import httpx

from agent_observability_studio.models import (
    SessionCreate,
    SessionUpdate,
    InteractionCreate,
    SessionStatus,
    InteractionType,
)


class ObservabilityClient:
    """Client for logging agent interactions to the observability platform."""

    def __init__(
        self, api_url: str = "http://localhost:8000", timeout: float = 5.0
    ):
        """Initialize client.

        Args:
            api_url: Base URL of the observability API
            timeout: Request timeout in seconds
        """
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def start_session(
        self,
        agent_name: str,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent_session_id: Optional[UUID] = None,
    ) -> UUID:
        """Start a new agent session.

        Args:
            agent_name: Name of the agent
            task_id: Optional task identifier
            metadata: Optional metadata dictionary
            parent_session_id: Optional parent session for nested agents

        Returns:
            Session UUID
        """
        session_data = SessionCreate(
            agent_name=agent_name,
            task_id=task_id,
            metadata=metadata or {},
            parent_session_id=parent_session_id,
        )

        response = self.client.post(
            f"{self.api_url}/api/v1/sessions",
            json=session_data.model_dump(mode="json"),
        )
        response.raise_for_status()

        return UUID(response.json()["id"])

    def end_session(
        self,
        session_id: UUID,
        status: SessionStatus = SessionStatus.SUCCESS,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """End an agent session.

        Args:
            session_id: Session UUID to end
            status: Final status of the session
            metadata: Optional additional metadata
        """
        update_data = SessionUpdate(
            status=status, end_time=datetime.utcnow(), metadata=metadata
        )

        response = self.client.patch(
            f"{self.api_url}/api/v1/sessions/{session_id}",
            json=update_data.model_dump(mode="json", exclude_none=True),
        )
        response.raise_for_status()

    def log_interaction(
        self,
        session_id: UUID,
        request: Dict[str, Any],
        response: Dict[str, Any],
        tokens_used: int,
        cost_usd: float = 0.0,
        latency_ms: Optional[int] = None,
        model: Optional[str] = None,
        error: Optional[str] = None,
        interaction_type: InteractionType = InteractionType.LLM_CALL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Log an interaction within a session.

        Args:
            session_id: Session UUID this interaction belongs to
            request: Request data (e.g., prompt, messages)
            response: Response data (e.g., completion, tool output)
            tokens_used: Number of tokens consumed
            cost_usd: Cost in USD
            latency_ms: Latency in milliseconds
            model: Model identifier
            error: Error message if interaction failed
            interaction_type: Type of interaction
            metadata: Optional additional metadata

        Returns:
            Interaction UUID
        """
        interaction_data = InteractionCreate(
            session_id=session_id,
            type=interaction_type,
            request=request,
            response=response,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            model=model,
            error=error,
            metadata=metadata or {},
        )

        response = self.client.post(
            f"{self.api_url}/api/v1/interactions",
            json=interaction_data.model_dump(mode="json"),
        )
        response.raise_for_status()

        return UUID(response.json()["id"])

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.client.close()
