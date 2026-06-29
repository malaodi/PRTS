"""Studio API — file browser for asset outputs, organized by type and user."""

import os
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.space import SpaceMember, Space
from app.api.deps import get_current_user, get_current_space_id, require_space_member

router = APIRouter(prefix="/studio", tags=["studio"])

DATA_ROOT = "/data/files"


@router.get("/browse")
async def browse_studio(
    path: str = Query("", description="Relative path within the studio"),
    user: str | None = Query(None, description="Filter by user (team mode)"),
    space_id: UUID | None = Depends(get_current_space_id),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    """Browse files in the studio, organized by asset type folders."""
    actual_space_id = str(space_id or member.space_id)
    base = os.path.join(DATA_ROOT, actual_space_id)

    if user:
        users_dir = os.path.join(base, "users", user)
        if not os.path.isdir(users_dir):
            return {"entries": [], "path": path, "user": user}
        full_path = os.path.join(users_dir, path) if path else users_dir
    else:
        full_path = os.path.join(base, path) if path else base

    full_path = os.path.normpath(full_path)
    if not full_path.startswith(os.path.normpath(base)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(full_path):
        return {"entries": [], "path": path}

    entries = []
    if os.path.isdir(full_path):
        for entry in sorted(os.listdir(full_path)):
            entry_path = os.path.join(full_path, entry)
            is_dir = os.path.isdir(entry_path)
            stat = os.stat(entry_path)
            entries.append({
                "name": entry,
                "type": "directory" if is_dir else "file",
                "size": stat.st_size if not is_dir else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    else:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read(50000)
        return {"file": entry, "content": content, "path": path}

    return {"entries": entries, "path": path}


@router.get("/team")
async def team_studio(
    space_id: UUID | None = Depends(get_current_space_id),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    """List team members for the studio view."""
    actual_space_id = space_id or member.space_id

    result = await db.execute(
        select(SpaceMember).where(SpaceMember.space_id == actual_space_id)
    )
    members = result.scalars().all()

    users = []
    for m in members:
        user_result = await db.execute(select(User).where(User.id == m.user_id))
        u = user_result.scalar_one_or_none()
        if u:
            users.append({
                "user_id": str(u.id),
                "display_name": u.display_name or u.username,
                "role": m.role.value if hasattr(m.role, 'value') else str(m.role),
            })

    return {"members": users}


def _sniff_asset_type(item: str) -> str:
    """Guess asset type folder name from filename."""
    if item.startswith("skills") or item == "skills":
        return "skill"
    if item.startswith("tools") or item == "tools":
        return "tool"
    if item.startswith("subagents") or item == "subagents":
        return "subagent"
    if item.startswith("mcp"):
        return "mcp"
    if item.startswith("widgets") or item == "widgets":
        return "widget"
    if item.startswith("pipelines") or item == "pipelines":
        return "pipeline"
    if item.startswith("packs") or item == "packs":
        return "pack"
    if item.startswith("sessions") or item == "sessions":
        return "session"
    return "other"
