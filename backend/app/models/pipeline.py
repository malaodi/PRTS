import uuid
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from app.database import Base


class TriggerType(str, enum.Enum):
    CRON = "cron"
    WEBHOOK = "webhook"
    EVENT = "event"


class PipelineStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    DELETED = "deleted"


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    trigger_type: Mapped[TriggerType] = mapped_column(String(20), nullable=False)
    trigger_config: Mapped[dict | None] = mapped_column(JSONB)
    task_design: Mapped[str] = mapped_column(Text, nullable=False)
    variables_schema: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[PipelineStatus] = mapped_column(String(20), default=PipelineStatus.ACTIVE)
    visibility: Mapped[str] = mapped_column(String(20), default="private", nullable=False, index=True)
    tags: Mapped[str | None] = mapped_column(Text)
    published_version: Mapped[str | None] = mapped_column(String(50))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requires_connections: Mapped[list | None] = mapped_column(JSONB)

    max_iterations: Mapped[int] = mapped_column(Integer, default=50)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)

    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="running")
    result_summary: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    thread_id: Mapped[str | None] = mapped_column(String(200))

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
