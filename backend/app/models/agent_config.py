import uuid
import os
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    prompt_file: Mapped[str | None] = mapped_column(String(500))
    model: Mapped[str] = mapped_column(String(100), default="gpt-4")
    release_policy: Mapped[str] = mapped_column(String(20), default="auto")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    space = relationship("Space")

    def get_prompt_content(self) -> str | None:
        """Get the system prompt, preferring file-based over inline."""
        if self.system_prompt and self.system_prompt.strip():
            return self.system_prompt

        if self.prompt_file and os.path.isfile(self.prompt_file):
            try:
                with open(self.prompt_file, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass

        prompts_dir = f"/data/files/{self.space_id}/agents/{self.id}"
        agents_md = os.path.join(prompts_dir, "agents.md")
        if os.path.isfile(agents_md):
            try:
                with open(agents_md, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass

        return None
