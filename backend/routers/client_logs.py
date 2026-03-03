"""
Endpoint for receiving client-side (frontend) error reports.

The frontend logger sends errors here so they appear in the same
centralized log files as backend errors, making debugging seamless.
"""

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from core.logging_config import get_logger

router = APIRouter()
logger = get_logger("compsphere.frontend")


class ClientLogEntry(BaseModel):
    level: str  # "error", "warn", "info"
    message: str
    stack: Optional[str] = None
    url: Optional[str] = None
    component: Optional[str] = None
    user_agent: Optional[str] = None
    extra: Optional[dict] = None


@router.post("", status_code=204)
async def receive_client_log(entry: ClientLogEntry, request: Request):
    """Receive and log a frontend error report."""
    client_ip = request.client.host if request.client else "-"

    log_extra = {
        "client_ip": client_ip,
        "error_context": f"url={entry.url} component={entry.component}",
    }

    msg = f"[FRONTEND] {entry.message}"
    if entry.stack:
        msg += f"\n  Stack: {entry.stack}"
    if entry.extra:
        msg += f"\n  Extra: {entry.extra}"

    level = entry.level.upper()
    if level == "ERROR":
        logger.error(msg, extra=log_extra)
    elif level == "WARN":
        logger.warning(msg, extra=log_extra)
    else:
        logger.info(msg, extra=log_extra)
