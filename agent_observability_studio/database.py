"""Database configuration and models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Enum,
    JSON,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from agent_observability_studio.models import SessionStatus, InteractionType


Base = declarative_base()


class SessionDB(Base):
    """Database model for sessions."""

    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name = Column(String, nullable=False, index=True)
    task_id = Column(String, nullable=True, index=True)
    status = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.ACTIVE)
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    end_time = Column(DateTime, nullable=True)
    total_tokens = Column(Integer, nullable=False, default=0)
    total_cost_usd = Column(Float, nullable=False, default=0.0)
    metadata = Column(JSON, nullable=False, default=dict)
    parent_session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=True)

    interactions = relationship("InteractionDB", back_populates="session", cascade="all, delete")
    children = relationship("SessionDB", backref="parent", remote_side=[id])


class InteractionDB(Base):
    """Database model for interactions."""

    __tablename__ = "interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False, index=True
    )
    type = Column(Enum(InteractionType), nullable=False, default=InteractionType.LLM_CALL)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    request = Column(JSON, nullable=False)
    response = Column(JSON, nullable=False)
    tokens_used = Column(Integer, nullable=False)
    cost_usd = Column(Float, nullable=False, default=0.0)
    latency_ms = Column(Integer, nullable=True)
    model = Column(String, nullable=True, index=True)
    error = Column(String, nullable=True)
    metadata = Column(JSON, nullable=False, default=dict)

    session = relationship("SessionDB", back_populates="interactions")


class Database:
    """Database connection manager."""

    def __init__(self, database_url: str = "sqlite:///./agent_studio.db"):
        self.engine = create_engine(
            database_url, connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def get_session(self):
        """Get database session."""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
