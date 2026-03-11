import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.logging_config import get_logger
from models.database import async_session_factory
from models.session import AgentSession
from models.task import Task
from services.docker_manager import DockerManager

logger = get_logger("compsphere.session")


class SessionManager:
    """Manages the lifecycle of agent sessions and their sandbox containers."""

    def __init__(self, docker_manager: DockerManager):
        self.docker_manager = docker_manager
        self.max_sessions = settings.MAX_CONCURRENT_SESSIONS
        self._active_sessions: dict[str, dict] = {}

    async def create_session(self, task_id: str, user_id: str) -> dict:
        """Create a new agent session with a sandbox container."""
        log_extra = {"task_id": task_id}

        if len(self._active_sessions) >= self.max_sessions:
            logger.warning(
                f"Session limit reached ({self.max_sessions}), rejecting task {task_id[:8]}",
                extra=log_extra,
            )
            raise ValueError(
                f"Maximum concurrent sessions ({self.max_sessions}) reached. "
                "Please wait for an existing session to finish."
            )

        session_id = str(uuid.uuid4())
        log_extra["session_id"] = session_id

        logger.info(f"Creating session {session_id[:8]} for task {task_id[:8]}", extra=log_extra)

        try:
            container_info = await self.docker_manager.create_container(
                user_id=user_id,
                session_id=session_id,
            )
        except Exception as e:
            logger.error(
                f"Failed to create container for session {session_id[:8]}: {e}",
                exc_info=True,
                extra=log_extra,
            )
            raise

        # Persist the session to the database
        try:
            async with async_session_factory() as db:
                agent_session = AgentSession(
                    id=uuid.UUID(session_id),
                    task_id=uuid.UUID(task_id),
                    container_id=container_info["container_id"],
                    vnc_port=container_info["vnc_port"],
                    status="running",
                )
                db.add(agent_session)

                await db.execute(
                    update(Task)
                    .where(Task.id == uuid.UUID(task_id))
                    .values(status="running")
                )
                await db.commit()
        except Exception as e:
            logger.error(
                f"Failed to persist session {session_id[:8]} to DB: {e}",
                exc_info=True,
                extra=log_extra,
            )
            # Clean up the container since DB save failed
            await self.docker_manager.destroy_container(container_info["container_id"])
            raise

        session_info = {
            "session_id": session_id,
            "task_id": task_id,
            "user_id": user_id,
            "container_id": container_info["container_id"],
            "container_name": container_info["container_name"],
            "vnc_port": container_info["vnc_port"],
            "status": "running",
        }
        self._active_sessions[session_id] = session_info

        logger.info(
            f"Session {session_id[:8]} created "
            f"(container={container_info['container_id'][:12]}, vnc_port={container_info['vnc_port']})",
            extra={**log_extra, "container_id": container_info["container_id"][:12]},
        )
        return session_info

    def get_session(self, session_id: str) -> Optional[dict]:
        return self._active_sessions.get(session_id)

    def list_active_sessions(self) -> list[dict]:
        return list(self._active_sessions.values())

    def get_active_count(self) -> int:
        return len(self._active_sessions)

    async def update_agent_status(self, session_id: str, new_status: str):
        """Update the agent's status (running/idle) without completing the session."""
        session_info = self._active_sessions.get(session_id)
        if session_info is None:
            return

        session_info["status"] = new_status
        task_id = session_info.get("task_id")

        try:
            async with async_session_factory() as db:
                await db.execute(
                    update(AgentSession)
                    .where(AgentSession.id == uuid.UUID(session_id))
                    .values(status=new_status)
                )
                if task_id:
                    await db.execute(
                        update(Task)
                        .where(Task.id == uuid.UUID(task_id))
                        .values(status=new_status)
                    )
                await db.commit()
        except Exception as e:
            logger.error(
                f"Failed to update session {session_id[:8]} to {new_status}: {e}",
                exc_info=True,
                extra={"session_id": session_id},
            )

        logger.debug(
            f"Session {session_id[:8]} status -> {new_status}",
            extra={"session_id": session_id, "task_id": task_id},
        )

    async def complete_agent(self, session_id: str):
        """Mark the agent as finished but keep the container running.

        The container stays alive so the user can still view/control the
        browser.  It will only be torn down when the user deletes the task
        (via ``destroy_session``).
        """
        log_extra = {"session_id": session_id}
        session_info = self._active_sessions.get(session_id)
        if session_info is None:
            return

        session_info["status"] = "completed"
        task_id = session_info.get("task_id")
        log_extra["task_id"] = task_id

        try:
            async with async_session_factory() as db:
                await db.execute(
                    update(AgentSession)
                    .where(AgentSession.id == uuid.UUID(session_id))
                    .values(status="completed")
                )
                if task_id:
                    await db.execute(
                        update(Task)
                        .where(Task.id == uuid.UUID(task_id))
                        .values(status="completed")
                    )
                await db.commit()
        except Exception as e:
            logger.error(
                f"Failed to mark session {session_id[:8]} as completed: {e}",
                exc_info=True,
                extra=log_extra,
            )

        logger.info(f"Session {session_id[:8]} agent completed, container kept alive", extra=log_extra)

    async def destroy_session(self, session_id: str):
        """Tear down a session: stop the container and update the database."""
        log_extra = {"session_id": session_id}
        session_info = self._active_sessions.pop(session_id, None)

        if session_info is None:
            logger.warning(f"Session {session_id[:8]} not found in active sessions", extra=log_extra)
            return

        container_id = session_info.get("container_id")
        task_id = session_info.get("task_id")
        log_extra["task_id"] = task_id

        if container_id:
            logger.info(f"Destroying container for session {session_id[:8]}", extra=log_extra)
            await self.docker_manager.destroy_container(container_id)

        try:
            async with async_session_factory() as db:
                now = datetime.now(timezone.utc)
                await db.execute(
                    update(AgentSession)
                    .where(AgentSession.id == uuid.UUID(session_id))
                    .values(status="completed", ended_at=now)
                )
                if task_id:
                    await db.execute(
                        update(Task)
                        .where(Task.id == uuid.UUID(task_id))
                        .values(status="completed")
                    )
                await db.commit()
        except Exception as e:
            logger.error(
                f"Failed to update DB for destroyed session {session_id[:8]}: {e}",
                exc_info=True,
                extra=log_extra,
            )

        logger.info(f"Session {session_id[:8]} destroyed", extra=log_extra)
