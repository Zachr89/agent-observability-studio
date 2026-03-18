"""CLI for running the observability platform."""

import argparse
import uvicorn


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Agent Observability Studio CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    if args.command == "serve":
        uvicorn.run(
            "agent_observability_studio.api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
