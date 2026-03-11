import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from core.logging_config import get_logger
from models.database import get_db
from models.session import AgentMessage, AgentSession
from models.task import Task
from models.user import User
from routers.auth import get_current_user
from services.agent_message_queue import agent_message_queue_registry
from services.message_bus import message_bus

router = APIRouter()
logger = get_logger("compsphere.tasks")

# Set by main.py after service initialization
session_manager = None
agent_orchestrator = None


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    name: Optional[str] = None
    prompt: str


class MessageCreate(BaseModel):
    content: str


class AgentMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[str] = None
    tool_result: Optional[str] = None
    sequence_num: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    container_id: Optional[str] = None
    vnc_port: Optional[int] = None
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    messages: list[AgentMessageResponse] = []

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    prompt: str
    status: str
    result_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskDetailResponse(TaskResponse):
    sessions: list[SessionResponse] = []
    vnc_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = Task(
        user_id=current_user.id,
        name=body.name or body.prompt[:80],
        prompt=body.prompt,
    )
    db.add(task)
    # Commit immediately so the background task can see the row in a
    # separate DB session (PostgreSQL read-committed isolation).
    await db.commit()
    await db.refresh(task)

    task_id_str = str(task.id)
    user_id_str = str(current_user.id)
    log_extra = {"task_id": task_id_str}

    logger.info(
        f"Task created: {task_id_str[:8]} by user {user_id_str[:8]} - \"{body.prompt[:60]}\"",
        extra=log_extra,
    )

    # Start agent session in background if services are available
    if session_manager and agent_orchestrator:
        async def _run_agent_background():
            follow_up_queue = agent_message_queue_registry.create(task_id_str)
            try:
                session_info = await session_manager.create_session(
                    task_id=task_id_str, user_id=user_id_str
                )

                async def message_cb(msg):
                    await message_bus.publish(task_id_str, msg)

                async def status_cb(new_status: str):
                    await session_manager.update_agent_status(
                        session_info["session_id"], new_status
                    )

                await agent_orchestrator.run_agent(
                    task_prompt=body.prompt,
                    session_id=session_info["session_id"],
                    container_id=session_info["container_id"],
                    message_callback=message_cb,
                    status_callback=status_cb,
                    follow_up_queue=follow_up_queue,
                    anthropic_api_key=settings.ANTHROPIC_API_KEY,
                )
            except ValueError as e:
                logger.warning(
                    f"Could not start agent for task {task_id_str[:8]}: {e}",
                    extra=log_extra,
                )
            except Exception as e:
                logger.error(
                    f"Background agent failed for task {task_id_str[:8]}: {type(e).__name__}: {e}",
                    exc_info=True,
                    extra=log_extra,
                )
            finally:
                agent_message_queue_registry.remove(task_id_str)
                # Mark agent as done but keep the container alive
                if session_manager:
                    for sid, info in list(session_manager._active_sessions.items()):
                        if info.get("task_id") == task_id_str:
                            await session_manager.complete_agent(sid)
                            break

        asyncio.create_task(_run_agent_background())

    return task


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task)
        .where(Task.user_id == current_user.id)
        .order_by(Task.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id, Task.user_id == current_user.id)
        .options(
            selectinload(Task.sessions).selectinload(AgentSession.messages)
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Compute vnc_url from the active session (running or idle — the
    # container stays alive until the user deletes the task).
    vnc_url = None
    if session_manager:
        task_id_str = str(task_id)
        for sid, info in session_manager._active_sessions.items():
            if info.get("task_id") == task_id_str and info.get("status") in ("running", "idle", "completed"):
                vnc_url = f"/ws/vnc/{sid}"
                break

    resp = TaskDetailResponse.model_validate(task)
    resp.vnc_url = vnc_url
    return resp


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Signal agent to shut down gracefully, then tear down containers
    task_id_str = str(task_id)
    queue = agent_message_queue_registry.get(task_id_str)
    if queue:
        await queue.put(None)  # Sentinel for shutdown

    if session_manager:
        for sid, info in list(session_manager._active_sessions.items()):
            if info.get("task_id") == task_id_str:
                await session_manager.destroy_session(sid)

    await db.delete(task)
    await db.flush()

    logger.info(f"Task {str(task_id)[:8]} deleted by user {str(current_user.id)[:8]}", extra={"task_id": str(task_id)})


@router.post("/{task_id}/message", response_model=AgentMessageResponse)
async def send_message(
    task_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id, Task.user_id == current_user.id)
        .options(selectinload(Task.sessions))
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task.status not in ("running", "pending", "idle"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot send message to task with status '{task.status}'",
        )

    active_session = next(
        (s for s in task.sessions if s.status in ("running", "creating", "idle")),
        None,
    )
    if active_session is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active session for this task",
        )

    seq_result = await db.execute(
        select(AgentMessage.sequence_num)
        .where(AgentMessage.session_id == active_session.id)
        .order_by(AgentMessage.sequence_num.desc())
        .limit(1)
    )
    last_seq = seq_result.scalar_one_or_none() or 0

    message = AgentMessage(
        session_id=active_session.id,
        role="user",
        content=body.content,
        sequence_num=last_seq + 1,
    )
    db.add(message)
    await db.flush()
    await db.refresh(message)

    # Deliver to the running agent's follow-up queue so it actually
    # processes the message (not just persisted in DB).
    task_id_str = str(task_id)
    agent_queue = agent_message_queue_registry.get(task_id_str)
    if agent_queue is not None:
        await agent_queue.put(body.content)

    logger.info(
        f"Message sent to task {task_id_str[:8]} (seq={last_seq + 1})",
        extra={"task_id": task_id_str, "session_id": str(active_session.id)},
    )

    return message
