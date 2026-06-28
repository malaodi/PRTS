"""Agent management API - CRUD for Agent configurations with file-based prompts."""
import os
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.space import SpaceMember
from app.models.agent_config import Agent
from app.api.deps import get_current_user, get_current_space_id, require_space_member

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    model: str = "gpt-4"
    release_policy: str = "auto"


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    release_policy: str | None = None


class AgentOut(BaseModel):
    id: str
    space_id: str
    name: str
    description: str | None
    system_prompt: str | None
    model: str
    release_policy: str
    is_default: bool
    created_at: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AgentOut])
async def list_agents(
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    db: AsyncSession = Depends(get_db),
):
    conditions = [Agent.space_id == space_id] if space_id else []
    result = await db.execute(
        select(Agent).where(*conditions).order_by(desc(Agent.is_default), desc(Agent.created_at))
    )
    agents = result.scalars().all()
    return [
        AgentOut(
            id=str(a.id),
            space_id=str(a.space_id),
            name=a.name,
            description=a.description,
            system_prompt=a.system_prompt,
            model=a.model,
            release_policy=a.release_policy,
            is_default=a.is_default,
            created_at=a.created_at.isoformat() if a.created_at else None,
        )
        for a in agents
    ]


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    actual_space_id = space_id or member.space_id

    is_default = False
    existing = await db.execute(
        select(Agent).where(Agent.space_id == actual_space_id).limit(1)
    )
    if existing.scalar_one_or_none() is None:
        is_default = True

    agent = Agent(
        space_id=actual_space_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt or None,
        model=data.model,
        release_policy=data.release_policy,
        is_default=is_default,
        created_by=current_user.id,
    )
    db.add(agent)
    await db.flush()

    if data.system_prompt:
        prompt_dir = f"/data/files/{actual_space_id}/agents/{agent.id}"
        os.makedirs(prompt_dir, exist_ok=True)
        agents_md = os.path.join(prompt_dir, "agents.md")
        with open(agents_md, "w", encoding="utf-8") as f:
            f.write(data.system_prompt)

    return AgentOut(
        id=str(agent.id),
        space_id=str(agent.space_id),
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        model=agent.model,
        release_policy=agent.release_policy,
        is_default=agent.is_default,
        created_at=agent.created_at.isoformat() if agent.created_at else None,
    )


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return AgentOut(
        id=str(agent.id),
        space_id=str(agent.space_id),
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        model=agent.model,
        release_policy=agent.release_policy,
        is_default=agent.is_default,
        created_at=agent.created_at.isoformat() if agent.created_at else None,
    )


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: UUID,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if data.name is not None:
        agent.name = data.name
    if data.description is not None:
        agent.description = data.description
    if data.system_prompt is not None:
        agent.system_prompt = data.system_prompt
        prompt_dir = f"/data/files/{agent.space_id}/agents/{agent.id}"
        os.makedirs(prompt_dir, exist_ok=True)
        agents_md = os.path.join(prompt_dir, "agents.md")
        with open(agents_md, "w", encoding="utf-8") as f:
            f.write(data.system_prompt)
    if data.model is not None:
        agent.model = data.model
    if data.release_policy is not None:
        agent.release_policy = data.release_policy

    await db.flush()
    return AgentOut(
        id=str(agent.id),
        space_id=str(agent.space_id),
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        model=agent.model,
        release_policy=agent.release_policy,
        is_default=agent.is_default,
        created_at=agent.created_at.isoformat() if agent.created_at else None,
    )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent:
        await db.delete(agent)
