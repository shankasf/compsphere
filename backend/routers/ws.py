import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import settings
from core.logging_config import get_logger
from services.message_bus import message_bus
from services.vnc_proxy import vnc_proxy

router = APIRouter()
logger = get_logger("compsphere.ws")

# These are set by main.py after service initialisation so that the
# WebSocket handlers can access the shared singleton instances.
session_manager = None
agent_orchestrator = None


@router.websocket("/ws/agent/{task_id}")
async def agent_websocket(websocket: WebSocket, task_id: str):
    """WebSocket for streaming agent messages to the frontend."""
    await websocket.accept()
    log_extra = {"task_id": task_id, "ws_event": "agent"}

    logger.info(f"Agent WebSocket connected for task {task_id[:8]}", extra=log_extra)

    queue = message_bus.subscribe(task_id)

    async def _send_from_queue():
        """Forward messages from the bus to this WebSocket client."""
        try:
            while True:
                msg = await queue.get()
                await websocket.send_json(msg)
        except Exception:
            pass  # WebSocket closed or cancelled

    sender_task = asyncio.create_task(_send_from_queue())

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Invalid JSON from client on task {task_id[:8]}: {e}",
                    extra=log_extra,
                )
                continue

            if message.get("type") == "user_message":
                logger.debug(
                    f"Received user message for task {task_id[:8]}: "
                    f"{message.get('content', '')[:80]}",
                    extra=log_extra,
                )
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from task {task_id[:8]}", extra=log_extra)
    except Exception as e:
        logger.error(
            f"Agent WebSocket error for task {task_id[:8]}: {type(e).__name__}: {e}",
            exc_info=True,
            extra=log_extra,
        )
    finally:
        sender_task.cancel()
        message_bus.unsubscribe(task_id, queue)


@router.websocket("/ws/vnc/{session_id}")
async def vnc_websocket(websocket: WebSocket, session_id: str):
    """WebSocket proxy for NoVNC."""
    await websocket.accept(subprotocol="binary")
    log_extra = {"session_id": session_id, "ws_event": "vnc"}

    if session_manager is None:
        logger.error("VNC WebSocket: session_manager not initialised", extra=log_extra)
        await websocket.close(code=1011, reason="Server not ready")
        return

    session = session_manager.get_session(session_id)
    if session is None:
        logger.warning(f"VNC WebSocket: session {session_id[:8]} not found", extra=log_extra)
        await websocket.close(code=1008, reason="Session not found")
        return

    vnc_port = session.get("vnc_port")
    if not vnc_port:
        logger.warning(f"VNC WebSocket: no vnc_port for session {session_id[:8]}", extra=log_extra)
        await websocket.close(code=1008, reason="VNC port unavailable")
        return

    container_host = settings.DOCKER_HOST_IP
    logger.info(f"VNC WebSocket starting proxy for session {session_id[:8]} on {container_host}:{vnc_port}", extra=log_extra)
    await vnc_proxy(websocket, container_host, vnc_port)
