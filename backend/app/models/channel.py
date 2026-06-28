"""
IM Channel integration models and API stubs.
Supports three paths: CLI access suite, channel binding, custom group push.
Platforms: Feishu (Lark), DingTalk, WeChat Work.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class ChannelBinding(Base):
    __tablename__ = "channel_bindings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # feishu, dingtalk, wecom
    channel_type: Mapped[str] = mapped_column(String(20), nullable=False)  # cli_suite, channel, webhook
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB)
    webhook_url: Mapped[str | None] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CLAccessSuite(Base):
    __tablename__ = "cli_access_suites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cli_command: Mapped[str | None] = mapped_column(String(500))
    auth_config: Mapped[dict | None] = mapped_column(JSONB)
    cli_managed: Mapped[bool] = mapped_column(Boolean, default=True)
    is_installed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
