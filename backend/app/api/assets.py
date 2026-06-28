from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.space import SpaceMember
from app.models.asset import Asset, AssetType, AgentAssetBinding, BindStatus
from app.api.deps import get_current_user, get_current_space_id, require_space_member
from pydantic import BaseModel

router = APIRouter(prefix="/assets", tags=["assets"])


class AssetCreate(BaseModel):
    asset_type: str
    name: str
    description: str = ""
    config: dict | None = None


class AssetOut(BaseModel):
    id: str
    space_id: str
    asset_type: str
    name: str
    description: str | None
    config: dict | None
    created_at: str | None

    model_config = {"from_attributes": True}


class BindingSet(BaseModel):
    agent_id: str
    asset_id: str
    status: str = "enabled"


class BindingOut(BaseModel):
    id: str
    agent_id: str
    asset_id: str
    status: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AssetOut])
async def list_assets(
    asset_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    db: AsyncSession = Depends(get_db),
):
    conditions = [Asset.space_id == space_id] if space_id else []
    if asset_type:
        conditions.append(Asset.asset_type == asset_type)

    result = await db.execute(
        select(Asset).where(*conditions).order_by(Asset.created_at.desc())
    )
    assets = result.scalars().all()
    return [
        AssetOut(
            id=str(a.id),
            space_id=str(a.space_id),
            asset_type=a.asset_type.value if hasattr(a.asset_type, 'value') else a.asset_type,
            name=a.name,
            description=a.description,
            config=a.config,
            created_at=a.created_at.isoformat() if a.created_at else None,
        )
        for a in assets
    ]


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def create_asset(
    data: AssetCreate,
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    actual_space_id = space_id or member.space_id
    asset = Asset(
        space_id=actual_space_id,
        asset_type=AssetType(data.asset_type),
        name=data.name,
        description=data.description,
        config=data.config,
        created_by=current_user.id,
    )
    db.add(asset)
    await db.flush()
    return AssetOut(
        id=str(asset.id),
        space_id=str(asset.space_id),
        asset_type=asset.asset_type.value,
        name=asset.name,
        description=asset.description,
        config=asset.config,
        created_at=asset.created_at.isoformat() if asset.created_at else None,
    )


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return AssetOut(
        id=str(asset.id),
        space_id=str(asset.space_id),
        asset_type=asset.asset_type.value,
        name=asset.name,
        description=asset.description,
        config=asset.config,
        created_at=asset.created_at.isoformat() if asset.created_at else None,
    )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset:
        await db.delete(asset)


@router.get("/bindings/{agent_id}", response_model=list[BindingOut])
async def list_bindings(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentAssetBinding).where(AgentAssetBinding.agent_id == agent_id)
    )
    bindings = result.scalars().all()
    return [
        BindingOut(id=str(b.id), agent_id=b.agent_id, asset_id=str(b.asset_id), status=b.status.value)
        for b in bindings
    ]


@router.post("/bindings", response_model=BindingOut, status_code=status.HTTP_201_CREATED)
async def bind_asset(
    data: BindingSet,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(AgentAssetBinding).where(
            AgentAssetBinding.agent_id == data.agent_id,
            AgentAssetBinding.asset_id == UUID(data.asset_id),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Binding already exists")

    binding = AgentAssetBinding(
        agent_id=data.agent_id,
        asset_id=UUID(data.asset_id),
        status=BindStatus(data.status),
    )
    db.add(binding)
    await db.flush()
    return BindingOut(id=str(binding.id), agent_id=binding.agent_id, asset_id=str(binding.asset_id), status=binding.status.value)


@router.patch("/bindings/{binding_id}", response_model=BindingOut)
async def update_binding(
    binding_id: UUID,
    status: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentAssetBinding).where(AgentAssetBinding.id == binding_id))
    binding = result.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Binding not found")
    binding.status = BindStatus(status)
    await db.flush()
    return BindingOut(id=str(binding.id), agent_id=binding.agent_id, asset_id=str(binding.asset_id), status=binding.status.value)


@router.delete("/bindings/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unbind_asset(
    binding_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentAssetBinding).where(AgentAssetBinding.id == binding_id))
    binding = result.scalar_one_or_none()
    if binding:
        await db.delete(binding)
