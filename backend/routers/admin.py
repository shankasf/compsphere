"""Admin portal API: login, stats, usage logs, and real-time cost WebSocket."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.logging_config import get_logger
from models.database import async_session_factory, get_db
from models.session import AgentMessage, AgentSession
from models.task import Task
from models.usage import UsageLog
from models.user import User
from routers.auth import create_access_token, pwd_context
from services.cost_tracker import MODEL_PRICING, cost_tracker

router = APIRouter()
logger = get_logger("compsphere.admin")

# Hardcoded admin emails
ADMIN_EMAILS = {"sagar@callsphere.tech"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_admin: bool = True


class StatsResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    total_users: int
    total_tasks: int
    total_sessions: int
    active_sessions: int
    total_messages: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_cache_read_tokens: int
    total_cache_creation_tokens: int
    cache_hit_rate: float
    estimated_savings_usd: float
    cost_today: float
    cost_this_week: float
    cost_this_month: float
    model_pricing: dict


class UserUsage(BaseModel):
    user_id: str
    email: str
    task_count: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    last_active: datetime | None


class UsageLogEntry(BaseModel):
    id: str
    task_id: str
    session_id: str
    user_id: str
    user_email: str | None = None
    model: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    total_cost_usd: float
    duration_ms: int
    num_turns: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Admin auth helpers
# ---------------------------------------------------------------------------

def _is_admin_email(email: str) -> bool:
    return email.lower() in ADMIN_EMAILS


async def get_admin_user(token: str, db: AsyncSession) -> User:
    """Validate JWT and ensure user is admin."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authorized as admin",
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str | None = payload.get("sub")
        is_admin: bool = payload.get("is_admin", False)
        if user_id is None or not is_admin:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not _is_admin_email(user.email):
        raise credentials_exception
    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login", response_model=AdminToken)
async def admin_login(body: AdminLogin, db: AsyncSession = Depends(get_db)):
    if not _is_admin_email(body.email):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin account")

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None:
        # Auto-create admin user on first login
        user = User(
            email=body.email,
            password_hash=pwd_context.hash(body.password),
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        logger.info(f"Admin user auto-created: {body.email}")

    if not pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "is_admin": True})
    logger.info(f"Admin login: {body.email}")
    return AdminToken(access_token=token)


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    token: str = "",
    db: AsyncSession = Depends(get_db),
):
    await get_admin_user(token, db)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    # Counts
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_tasks = (await db.execute(select(func.count(Task.id)))).scalar() or 0
    total_sessions = (await db.execute(select(func.count(AgentSession.id)))).scalar() or 0
    active_sessions = (await db.execute(
        select(func.count(AgentSession.id)).where(
            AgentSession.status.in_(["running", "idle", "creating"])
        )
    )).scalar() or 0
    total_messages = (await db.execute(select(func.count(AgentMessage.id)))).scalar() or 0

    # Costs from usage_logs
    total_cost = (await db.execute(
        select(func.coalesce(func.sum(UsageLog.total_cost_usd), 0.0))
    )).scalar() or 0.0
    total_input = (await db.execute(
        select(func.coalesce(func.sum(UsageLog.input_tokens), 0))
    )).scalar() or 0
    total_output = (await db.execute(
        select(func.coalesce(func.sum(UsageLog.output_tokens), 0))
    )).scalar() or 0
    total_cache_read = (await db.execute(
        select(func.coalesce(func.sum(UsageLog.cache_read_tokens), 0))
    )).scalar() or 0
    total_cache_creation = (await db.execute(
        select(func.coalesce(func.sum(UsageLog.cache_creation_tokens), 0))
    )).scalar() or 0

    # Cache hit rate: cache_read / (input + cache_read + cache_creation)
    total_input_side = total_input + total_cache_read + total_cache_creation
    cache_hit_rate = (
        total_cache_read / total_input_side if total_input_side > 0 else 0.0
    )

    # Estimated savings from caching
    savings_info = cost_tracker.calculate_cache_savings(
        input_tokens=total_input,
        output_tokens=total_output,
        cache_read_tokens=total_cache_read,
        cache_creation_tokens=total_cache_creation,
    )

    cost_today = (await db.execute(
        select(func.coalesce(func.sum(UsageLog.total_cost_usd), 0.0)).where(
            UsageLog.created_at >= today_start
        )
    )).scalar() or 0.0
    cost_week = (await db.execute(
        select(func.coalesce(func.sum(UsageLog.total_cost_usd), 0.0)).where(
            UsageLog.created_at >= week_start
        )
    )).scalar() or 0.0
    cost_month = (await db.execute(
        select(func.coalesce(func.sum(UsageLog.total_cost_usd), 0.0)).where(
            UsageLog.created_at >= month_start
        )
    )).scalar() or 0.0

    return StatsResponse(
        total_users=total_users,
        total_tasks=total_tasks,
        total_sessions=total_sessions,
        active_sessions=active_sessions,
        total_messages=total_messages,
        total_cost_usd=round(float(total_cost), 6),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cache_read_tokens=total_cache_read,
        total_cache_creation_tokens=total_cache_creation,
        cache_hit_rate=round(cache_hit_rate, 4),
        estimated_savings_usd=round(savings_info["savings"], 6),
        cost_today=round(float(cost_today), 6),
        cost_this_week=round(float(cost_week), 6),
        cost_this_month=round(float(cost_month), 6),
        model_pricing=MODEL_PRICING,
    )


@router.get("/users")
async def get_users(
    token: str = "",
    db: AsyncSession = Depends(get_db),
):
    await get_admin_user(token, db)

    # Get all users with their usage stats
    users_result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = users_result.scalars().all()

    user_usage_list = []
    for user in users:
        uid = user.id
        task_count = (await db.execute(
            select(func.count(Task.id)).where(Task.user_id == uid)
        )).scalar() or 0

        user_cost = (await db.execute(
            select(func.coalesce(func.sum(UsageLog.total_cost_usd), 0.0)).where(
                UsageLog.user_id == uid
            )
        )).scalar() or 0.0
        user_input = (await db.execute(
            select(func.coalesce(func.sum(UsageLog.input_tokens), 0)).where(
                UsageLog.user_id == uid
            )
        )).scalar() or 0
        user_output = (await db.execute(
            select(func.coalesce(func.sum(UsageLog.output_tokens), 0)).where(
                UsageLog.user_id == uid
            )
        )).scalar() or 0

        last_task = (await db.execute(
            select(Task.updated_at).where(Task.user_id == uid).order_by(Task.updated_at.desc()).limit(1)
        )).scalar()

        user_usage_list.append(UserUsage(
            user_id=str(uid),
            email=user.email,
            task_count=task_count,
            total_cost_usd=round(float(user_cost), 6),
            total_input_tokens=user_input,
            total_output_tokens=user_output,
            last_active=last_task,
        ))

    return user_usage_list


@router.get("/usage")
async def get_usage_logs(
    token: str = "",
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    await get_admin_user(token, db)

    result = await db.execute(
        select(UsageLog)
        .order_by(UsageLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = result.scalars().all()

    # Get user emails for display
    user_ids = {log.user_id for log in logs}
    users_result = await db.execute(
        select(User.id, User.email).where(User.id.in_(user_ids))
    )
    email_map = {str(row[0]): row[1] for row in users_result.all()}

    return [
        UsageLogEntry(
            id=str(log.id),
            task_id=str(log.task_id),
            session_id=log.session_id,
            user_id=str(log.user_id),
            user_email=email_map.get(str(log.user_id)),
            model=log.model,
            input_tokens=log.input_tokens or 0,
            output_tokens=log.output_tokens or 0,
            cache_read_tokens=log.cache_read_tokens or 0,
            cache_creation_tokens=log.cache_creation_tokens or 0,
            total_cost_usd=round(float(log.total_cost_usd or 0), 6),
            duration_ms=log.duration_ms or 0,
            num_turns=log.num_turns or 0,
            created_at=log.created_at,
        )
        for log in logs
    ]


# ---------------------------------------------------------------------------
# Real-time WebSocket for admin cost updates
# ---------------------------------------------------------------------------

@router.websocket("/ws/costs")
async def admin_costs_websocket(websocket: WebSocket):
    """WebSocket that pushes real-time cost updates to admin dashboard."""
    await websocket.accept()
    logger.info("Admin cost WebSocket connected")

    # Validate admin token from query params
    token = websocket.query_params.get("token", "")
    try:
        async with async_session_factory() as db:
            await get_admin_user(token, db)
    except HTTPException:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Send initial state
    await websocket.send_json({
        "type": "init",
        **cost_tracker.get_cumulative(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    bus_queue = cost_tracker.subscribe()

    async def _send_updates():
        try:
            while True:
                msg = await bus_queue.get()
                await websocket.send_json(msg)
        except Exception:
            pass

    sender_task = asyncio.create_task(_send_updates())

    try:
        while True:
            # Keep connection alive; handle client pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("Admin cost WebSocket disconnected")
    except Exception as e:
        logger.error(f"Admin WebSocket error: {type(e).__name__}: {e}")
    finally:
        sender_task.cancel()
        cost_tracker.unsubscribe(bus_queue)
