"""
IM Channel integration API - Feishu/DingTalk/WeCom binding management.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.space import SpaceMember
from app.models.channel import ChannelBinding, CLAccessSuite
from app.api.deps import get_current_user, get_current_space_id, require_space_member

router = APIRouter(prefix="/channels", tags=["channels"])


class ChannelCreate(BaseModel):
    platform: str
    channel_type: str
    name: str
    agent_id: str | None = None
    config: dict | None = None
    webhook_url: str | None = None


class ChannelOut(BaseModel):
    id: str
    platform: str
    channel_type: str
    name: str
    agent_id: str | None
    is_active: bool
    webhook_url: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ChannelOut])
async def list_channels(
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    db: AsyncSession = Depends(get_db),
):
    conditions = [ChannelBinding.space_id == space_id] if space_id else []
    result = await db.execute(select(ChannelBinding).where(*conditions))
    bindings = result.scalars().all()
    return [
        ChannelOut(
            id=str(b.id),
            platform=b.platform,
            channel_type=b.channel_type,
            name=b.name,
            agent_id=str(b.agent_id) if b.agent_id else None,
            is_active=b.is_active,
            webhook_url=b.webhook_url,
        )
        for b in bindings
    ]


@router.post("", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
async def create_channel(
    data: ChannelCreate,
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    actual_space_id = space_id or member.space_id

    channel = ChannelBinding(
        space_id=actual_space_id,
        platform=data.platform,
        channel_type=data.channel_type,
        name=data.name,
        agent_id=UUID(data.agent_id) if data.agent_id else None,
        config=data.config,
        webhook_url=data.webhook_url,
    )
    db.add(channel)
    await db.flush()

    return ChannelOut(
        id=str(channel.id),
        platform=channel.platform,
        channel_type=channel.channel_type,
        name=channel.name,
        agent_id=str(channel.agent_id) if channel.agent_id else None,
        is_active=channel.is_active,
        webhook_url=channel.webhook_url,
    )


@router.patch("/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: UUID,
    is_active: bool | None = None,
    webhook_url: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ChannelBinding).where(ChannelBinding.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    if is_active is not None:
        channel.is_active = is_active
    if webhook_url is not None:
        channel.webhook_url = webhook_url

    await db.flush()
    return ChannelOut(
        id=str(channel.id),
        platform=channel.platform,
        channel_type=channel.channel_type,
        name=channel.name,
        agent_id=str(channel.agent_id) if channel.agent_id else None,
        is_active=channel.is_active,
        webhook_url=channel.webhook_url,
    )


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ChannelBinding).where(ChannelBinding.id == channel_id))
    channel = result.scalar_one_or_none()
    if channel:
        await db.delete(channel)
