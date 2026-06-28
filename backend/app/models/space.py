import uuid
from datetime import datetime
from enum import StrEnum
from sqlalchemy import String, DateTime, func, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class SpaceType(StrEnum):
    PERSONAL = "personal"
    TEAM = "team"


class MemberRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Space(Base):
    __tablename__ = "spaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[SpaceType] = mapped_column(String(20), default=SpaceType.PERSONAL, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    team_context: Mapped[str | None] = mapped_column(String(2000))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner = relationship("User", back_populates="owned_spaces", foreign_keys=[owner_id])
    members = relationship("SpaceMember", back_populates="space", cascade="all, delete-orphan")
    member_count: Mapped[int] = mapped_column(default=1, server_default="1")


class SpaceMember(Base):
    __tablename__ = "space_members"
    __table_args__ = (
        UniqueConstraint("space_id", "user_id", name="uq_space_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    role: Mapped[MemberRole] = mapped_column(String(20), default=MemberRole.MEMBER, nullable=False)

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    space = relationship("Space", back_populates="members")
    user = relationship("User", back_populates="space_memberships")
