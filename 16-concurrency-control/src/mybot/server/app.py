"""server/app.py -- FastAPI application factory."""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from mybot.core.context import AppContext


def create_app(context: "AppContext") -> FastAPI:
    """Build and return the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Workers are started externally (in main.py) before uvicorn boots.
        yield
        # Cleanup handled by main.py finally block.

    app = FastAPI(
        title="my-bot WebSocket API",
        description="Programmatic access to your BuckClaw agent via WebSocket.",
        version="0.11.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> JSONResponse:
        """Health check endpoint."""
        ws_worker = getattr(context, "websocket_worker", None)
        return JSONResponse({
            "status": "ok",
            "agent": context.config.agent.name,
            "ws_clients": len(ws_worker.clients) if ws_worker else 0,
        })

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket endpoint -- send JSON, receive event broadcasts."""
        await websocket.accept()
        ws_worker = getattr(context, "websocket_worker", None)
        if ws_worker is None:
            await websocket.close(code=1013, reason="WebSocket worker not available")
            return
        try:
            await ws_worker.handle_connection(websocket)
        except WebSocketDisconnect:
            pass

    return app
