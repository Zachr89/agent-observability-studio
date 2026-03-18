"""FastAPI application for observability platform."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from agent_observability_studio.database import Database, SessionDB, InteractionDB
from agent_observability_studio.models import (
    Session as SessionModel,
    Interaction as InteractionModel,
    SessionCreate,
    SessionUpdate,
    InteractionCreate,
    SessionQuery,
    SessionStatus,
    CostBreakdown,
    DecisionNode,
)
from agent_observability_studio.websocket_manager import ConnectionManager
from agent_observability_studio.config import get_settings


settings = get_settings()
db_manager = Database(settings.database_url)
app = FastAPI(title="Agent Observability Studio", version="0.1.0")
ws_manager = ConnectionManager()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    """Dependency to get database session."""
    return next(db_manager.get_session())


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Agent Observability Studio",
        "version": "0.1.0",
        "endpoints": {
            "api": "/api/v1",
            "docs": "/docs",
            "websocket": "/ws",
            "ui": "/ui",
        },
    }


@app.post("/api/v1/sessions", response_model=SessionModel)
async def create_session(
    session_data: SessionCreate, db: Session = Depends(get_db)
) -> SessionModel:
    """Create a new agent session."""
    db_session = SessionDB(
        agent_name=session_data.agent_name,
        task_id=session_data.task_id,
        metadata=session_data.metadata,
        parent_session_id=session_data.parent_session_id,
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    session_model = SessionModel(
        id=db_session.id,
        agent_name=db_session.agent_name,
        task_id=db_session.task_id,
        status=db_session.status,
        start_time=db_session.start_time,
        end_time=db_session.end_time,
        total_tokens=db_session.total_tokens,
        total_cost_usd=db_session.total_cost_usd,
        metadata=db_session.metadata,
        parent_session_id=db_session.parent_session_id,
    )

    await ws_manager.broadcast(
        {"type": "session_created", "session": session_model.model_dump(mode="json")}
    )

    return session_model


@app.patch("/api/v1/sessions/{session_id}", response_model=SessionModel)
async def update_session(
    session_id: UUID, update_data: SessionUpdate, db: Session = Depends(get_db)
) -> SessionModel:
    """Update an existing session."""
    db_session = db.query(SessionDB).filter(SessionDB.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    if update_data.status:
        db_session.status = update_data.status
    if update_data.end_time:
        db_session.end_time = update_data.end_time
    if update_data.metadata:
        db_session.metadata.update(update_data.metadata)

    db.commit()
    db.refresh(db_session)

    session_model = SessionModel(
        id=db_session.id,
        agent_name=db_session.agent_name,
        task_id=db_session.task_id,
        status=db_session.status,
        start_time=db_session.start_time,
        end_time=db_session.end_time,
        total_tokens=db_session.total_tokens,
        total_cost_usd=db_session.total_cost_usd,
        metadata=db_session.metadata,
        parent_session_id=db_session.parent_session_id,
    )

    await ws_manager.broadcast(
        {"type": "session_updated", "session": session_model.model_dump(mode="json")}
    )

    return session_model


@app.get("/api/v1/sessions", response_model=List[SessionModel])
async def query_sessions(
    agent_name: Optional[str] = None,
    task_id: Optional[str] = None,
    status: Optional[SessionStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> List[SessionModel]:
    """Query sessions with filters."""
    query = db.query(SessionDB)

    if agent_name:
        query = query.filter(SessionDB.agent_name == agent_name)
    if task_id:
        query = query.filter(SessionDB.task_id == task_id)
    if status:
        query = query.filter(SessionDB.status == status)
    if start_date:
        query = query.filter(SessionDB.start_time >= start_date)
    if end_date:
        query = query.filter(SessionDB.start_time <= end_date)

    sessions = query.order_by(SessionDB.start_time.desc()).limit(limit).offset(offset).all()

    return [
        SessionModel(
            id=s.id,
            agent_name=s.agent_name,
            task_id=s.task_id,
            status=s.status,
            start_time=s.start_time,
            end_time=s.end_time,
            total_tokens=s.total_tokens,
            total_cost_usd=s.total_cost_usd,
            metadata=s.metadata,
            parent_session_id=s.parent_session_id,
        )
        for s in sessions
    ]


@app.get("/api/v1/sessions/{session_id}", response_model=SessionModel)
async def get_session(session_id: UUID, db: Session = Depends(get_db)) -> SessionModel:
    """Get a specific session by ID."""
    db_session = db.query(SessionDB).filter(SessionDB.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionModel(
        id=db_session.id,
        agent_name=db_session.agent_name,
        task_id=db_session.task_id,
        status=db_session.status,
        start_time=db_session.start_time,
        end_time=db_session.end_time,
        total_tokens=db_session.total_tokens,
        total_cost_usd=db_session.total_cost_usd,
        metadata=db_session.metadata,
        parent_session_id=db_session.parent_session_id,
    )


@app.post("/api/v1/interactions", response_model=InteractionModel)
async def log_interaction(
    interaction_data: InteractionCreate, db: Session = Depends(get_db)
) -> InteractionModel:
    """Log a new interaction for a session."""
    # Verify session exists
    db_session = (
        db.query(SessionDB).filter(SessionDB.id == interaction_data.session_id).first()
    )
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Create interaction
    db_interaction = InteractionDB(
        session_id=interaction_data.session_id,
        type=interaction_data.type,
        request=interaction_data.request,
        response=interaction_data.response,
        tokens_used=interaction_data.tokens_used,
        cost_usd=interaction_data.cost_usd,
        latency_ms=interaction_data.latency_ms,
        model=interaction_data.model,
        error=interaction_data.error,
        metadata=interaction_data.metadata,
    )
    db.add(db_interaction)

    # Update session totals
    db_session.total_tokens += interaction_data.tokens_used
    db_session.total_cost_usd += interaction_data.cost_usd

    db.commit()
    db.refresh(db_interaction)

    interaction_model = InteractionModel(
        id=db_interaction.id,
        session_id=db_interaction.session_id,
        type=db_interaction.type,
        timestamp=db_interaction.timestamp,
        request=db_interaction.request,
        response=db_interaction.response,
        tokens_used=db_interaction.tokens_used,
        cost_usd=db_interaction.cost_usd,
        latency_ms=db_interaction.latency_ms,
        model=db_interaction.model,
        error=db_interaction.error,
        metadata=db_interaction.metadata,
    )

    await ws_manager.broadcast(
        {"type": "interaction_logged", "interaction": interaction_model.model_dump(mode="json")}
    )

    return interaction_model


@app.get("/api/v1/sessions/{session_id}/interactions", response_model=List[InteractionModel])
async def get_session_interactions(
    session_id: UUID, db: Session = Depends(get_db)
) -> List[InteractionModel]:
    """Get all interactions for a session."""
    interactions = (
        db.query(InteractionDB)
        .filter(InteractionDB.session_id == session_id)
        .order_by(InteractionDB.timestamp)
        .all()
    )

    return [
        InteractionModel(
            id=i.id,
            session_id=i.session_id,
            type=i.type,
            timestamp=i.timestamp,
            request=i.request,
            response=i.response,
            tokens_used=i.tokens_used,
            cost_usd=i.cost_usd,
            latency_ms=i.latency_ms,
            model=i.model,
            error=i.error,
            metadata=i.metadata,
        )
        for i in interactions
    ]


@app.get("/api/v1/analytics/cost-breakdown", response_model=CostBreakdown)
async def get_cost_breakdown(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
) -> CostBreakdown:
    """Get cost breakdown analytics."""
    query = db.query(SessionDB)

    if start_date:
        query = query.filter(SessionDB.start_time >= start_date)
    if end_date:
        query = query.filter(SessionDB.start_time <= end_date)

    sessions = query.all()

    total_cost = sum(s.total_cost_usd for s in sessions)
    total_tokens = sum(s.total_tokens for s in sessions)

    by_agent = {}
    by_task = {}
    for s in sessions:
        by_agent[s.agent_name] = by_agent.get(s.agent_name, 0) + s.total_cost_usd
        if s.task_id:
            by_task[s.task_id] = by_task.get(s.task_id, 0) + s.total_cost_usd

    # Get model breakdown from interactions
    interactions = (
        db.query(InteractionDB.model, func.sum(InteractionDB.cost_usd))
        .filter(
            and_(
                InteractionDB.session_id.in_([s.id for s in sessions]),
                InteractionDB.model.isnot(None),
            )
        )
        .group_by(InteractionDB.model)
        .all()
    )
    by_model = {model: float(cost) for model, cost in interactions if model}

    time_range = (
        min(s.start_time for s in sessions) if sessions else datetime.utcnow(),
        max(s.start_time for s in sessions) if sessions else datetime.utcnow(),
    )

    return CostBreakdown(
        total_cost_usd=total_cost,
        total_tokens=total_tokens,
        by_agent=by_agent,
        by_model=by_model,
        by_task=by_task,
        time_range=time_range,
    )


@app.get("/api/v1/analytics/decision-tree", response_model=List[DecisionNode])
async def get_decision_tree(
    root_session_id: Optional[UUID] = None, db: Session = Depends(get_db)
) -> List[DecisionNode]:
    """Get decision tree for agent collaboration."""
    if root_session_id:
        root = db.query(SessionDB).filter(SessionDB.id == root_session_id).first()
        if not root:
            raise HTTPException(status_code=404, detail="Root session not found")
        sessions = [root] + _get_all_children(db, root.id)
    else:
        # Get all root sessions (no parent)
        sessions = db.query(SessionDB).filter(SessionDB.parent_session_id.is_(None)).all()

    nodes = []
    for s in sessions:
        children = (
            db.query(SessionDB.id)
            .filter(SessionDB.parent_session_id == s.id)
            .all()
        )
        nodes.append(
            DecisionNode(
                session_id=s.id,
                agent_name=s.agent_name,
                task_id=s.task_id,
                children=[c[0] for c in children],
                status=s.status,
                total_cost_usd=s.total_cost_usd,
                metadata=s.metadata,
            )
        )

    return nodes


def _get_all_children(db: Session, parent_id: UUID) -> List[SessionDB]:
    """Recursively get all child sessions."""
    children = db.query(SessionDB).filter(SessionDB.parent_session_id == parent_id).all()
    all_children = children.copy()
    for child in children:
        all_children.extend(_get_all_children(db, child.id))
    return all_children


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and receive client filters
            data = await websocket.receive_json()
            if data.get("type") == "filter":
                # Client can send filters to only receive certain events
                await websocket.send_json({"status": "filter_applied", "filters": data.get("filters", {})})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
