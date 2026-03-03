import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.database import Base


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    container_id = Column(String(100), nullable=True)
    vnc_port = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default="creating")
    started_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ended_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("Task", back_populates="sessions")
    messages = relationship(
        "AgentMessage", back_populates="session", cascade="all, delete-orphan",
        order_by="AgentMessage.sequence_num",
    )

    def __repr__(self):
        return f"<AgentSession {self.id} [{self.status}]>"


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=True)
    tool_name = Column(String(255), nullable=True)
    tool_input = Column(Text, nullable=True)
    tool_result = Column(Text, nullable=True)
    sequence_num = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session = relationship("AgentSession", back_populates="messages")

    def __repr__(self):
        return f"<AgentMessage seq={self.sequence_num} role={self.role}>"
