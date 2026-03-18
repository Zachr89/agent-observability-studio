# Agent Observability Studio

Real-time monitoring and debugging platform for multi-agent AI systems—Chrome DevTools for AI agents.

## What is this?

Agent Observability Studio provides deep inspection tools for multi-agent AI systems, complementing existing infrastructure dashboards. It captures live interaction traces, analyzes token costs, detects performance bottlenecks, and helps debug agent decision trees and failures in production environments.

## Features

- **Live Interaction Tracing** — Real-time visibility into agent conversations and inter-agent communication
- **Token Cost Analysis** — Granular per-agent, per-interaction token accounting with cost attribution
- **Performance Bottleneck Detection** — Automatic identification of slow agents, network delays, and processing inefficiencies
- **Decision Tree Inspection** — Visualize agent reasoning paths and fallback logic execution
- **Failure Analysis** — Capture and replay failed interactions with full context
- **WebSocket Streaming** — Push-based updates for low-latency monitoring
- **RESTful API** — Programmatic access to traces, metrics, and historical data
- **CLI Tools** — Command-line utilities for local debugging and integration

## Quick Start

### Installation

```bash
pip install agent-observability-studio
```

### Basic Setup

```python
from agent_observability_studio import ObservabilityClient

# Initialize the client
client = ObservabilityClient(
    api_url="http://localhost:8000",
    api_key="your-api-key"
)

# Start monitoring an agent interaction
trace = client.start_trace(
    agent_id="my-agent",
    session_id="session-123"
)

# Log a step
trace.log_step(
    name="retrieve_documents",
    duration_ms=245,
    tokens_used=1024,
    status="success"
)

# End trace
trace.end()
```

### CLI Usage

```bash
# Start the monitoring server
aos-server --port 8000 --db-url postgresql://localhost/observability

# Stream live traces
aos-trace watch

# Export session data
aos-export --session session-123 --format json --output trace.json

# Analyze costs
aos-costs --agent-id my-agent --date-range "2025-03-01:2025-03-18"
```

## Usage Examples

**Monitor agent costs in real-time:**
```python
trace = client.start_trace(agent_id="researcher")
# ... agent work ...
cost_report = trace.get_cost_summary()
print(f"Total tokens: {cost_report.total_tokens}")
print(f"Estimated cost: ${cost_report.estimated_cost:.4f}")
```

**Capture and replay failures:**
```python
failed_traces = client.query_traces(status="error", limit=10)
for trace in failed_traces:
    print(f"Error: {trace.error_message}")
    print(f"Decision tree: {trace.decision_path}")
```

**Subscribe to live events:**
```python
async def handle_trace(event):
    print(f"Trace {event.trace_id}: {event.status}")

client.subscribe("trace.completed", handle_trace)
```

## Tech Stack

- **Runtime**: Python 3.12+
- **API**: FastAPI with async support
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Real-time**: WebSocket streams via websockets library
- **Configuration**: Pydantic for settings management
- **CLI**: Click for command-line interface
- **Packaging**: Poetry for dependency management

## Architecture

The studio consists of four main components:

- **API Server** (`api.py`) — RESTful endpoints for trace queries and configuration
- **WebSocket Manager** (`websocket_manager.py`) — Real-time event streaming
- **Database Layer** (`database.py`) — Persistent storage of traces and metrics
- **Client SDK** (`client.py`) — Python library for agent instrumentation

## License

MIT