import uuid
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, Text, Integer, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class AssetType(str, enum.Enum):
    SKILL = "skill"
    TOOL = "tool"
    SUBAGENT = "subagent"
    MCP = "mcp"
    WIDGET = "widget"
    PACK = "pack"
    PIPELINE = "pipeline"


class AssetVisibility(str, enum.Enum):
    PRIVATE = "private"
    TEAM = "team"
    PUBLIC = "public"


class BindStatus(str, enum.Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    OPTIONAL = "optional"
    LOCKED = "locked"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    space_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type: Mapped[AssetType] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict | None] = mapped_column(JSONB)
    file_path: Mapped[str | None] = mapped_column(String(1000))

    visibility: Mapped[str] = mapped_column(String(20), default="private", nullable=False, index=True)
    tags: Mapped[str | None] = mapped_column(Text)
    published_version: Mapped[str | None] = mapped_column(String(50))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AgentAssetBinding(Base):
    __tablename__ = "agent_asset_bindings"
    __table_args__ = (
        UniqueConstraint("agent_id", "asset_id", name="uq_agent_asset"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[BindStatus] = mapped_column(String(20), default=BindStatus.ENABLED, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
