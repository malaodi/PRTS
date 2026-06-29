from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.database import get_db
from app.models.user import User
from app.models.space import SpaceMember
from app.models.asset import Asset, AssetType, AssetVisibility, AgentAssetBinding, BindStatus
from app.api.deps import get_current_user, get_current_space_id, require_space_member
from app.tools.asset_creator import get_pending_creation, get_pending_by_creation_id
from app.tools.marketplace_ops import index_asset_for_marketplace
from app.tools.vector_ops import embed_and_store
from pydantic import BaseModel

router = APIRouter(prefix="/assets", tags=["assets"])


class AssetCreate(BaseModel):
    asset_type: str
    name: str
    description: str = ""
    config: dict | None = None
    content: str = ""
    visibility: str = "private"
    tags: str = ""


class AssetOut(BaseModel):
    id: str
    space_id: str
    asset_type: str
    name: str
    description: str | None
    config: dict | None
    visibility: str | None
    tags: str | None
    published_version: str | None
    published_at: str | None
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


def _asset_to_out(a: Asset) -> AssetOut:
    return AssetOut(
        id=str(a.id),
        space_id=str(a.space_id),
        asset_type=a.asset_type.value if hasattr(a.asset_type, 'value') else a.asset_type,
        name=a.name,
        description=a.description,
        config=a.config,
        visibility=a.visibility if hasattr(a, 'visibility') else "private",
        tags=a.tags if hasattr(a, 'tags') else None,
        published_version=a.published_version if hasattr(a, 'published_version') else None,
        published_at=a.published_at.isoformat() if a.published_at else None,
        created_at=a.created_at.isoformat() if a.created_at else None,
    )


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
    return [_asset_to_out(a) for a in assets]


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def create_asset_endpoint(
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
        visibility=data.visibility,
        tags=data.tags or None,
        created_by=current_user.id,
    )
    db.add(asset)
    await db.flush()

    if data.content:
        _write_asset_file(str(actual_space_id), asset.id, data.asset_type, data.content)

    return _asset_to_out(asset)


@router.post("/confirm-pending", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def confirm_pending_creation(
    thread_id: str = Query("", description="The conversation thread ID"),
    creation_id: str = Query("", description="Or the creation ID from widget"),
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    pending = get_pending_creation(thread_id) if thread_id else None
    if not pending and creation_id:
        pending = get_pending_by_creation_id(creation_id)
    if not pending:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending asset creation for this thread")

    actual_space_id = str(space_id or member.space_id)
    asset = Asset(
        space_id=UUID(actual_space_id),
        asset_type=AssetType(pending["asset_type"]),
        name=pending["name"],
        description=pending.get("description", ""),
        visibility=pending.get("visibility", "private"),
        tags=",".join(pending.get("tags", [])) if pending.get("tags") else None,
        created_by=current_user.id,
    )
    db.add(asset)
    await db.flush()

    if pending.get("content"):
        _write_asset_file(actual_space_id, asset.id, pending["asset_type"], pending["content"])

    if pending.get("visibility") == "team":
        try:
            tag_list = pending.get("tags", [])
            team_text = f"名称: {pending['name']}\n类型: {pending['asset_type']}\n描述: {pending.get('description','')}\n标签: {', '.join(tag_list)}"
            metadata = {"asset_id": str(asset.id), "name": pending["name"], "asset_type": pending["asset_type"]}
            await embed_and_store(f"team_{actual_space_id}", [team_text], [metadata])
        except Exception:
            pass

    return _asset_to_out(asset)


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return _asset_to_out(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset:
        await db.delete(asset)


@router.post("/{asset_id}/publish", response_model=AssetOut)
async def publish_asset_to_marketplace(
    asset_id: UUID,
    current_user: User = Depends(get_current_user),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    type_val = asset.asset_type.value if hasattr(asset.asset_type, 'value') else str(asset.asset_type)
    content = _read_asset_file(str(asset.space_id), asset.id, type_val)
    review_text = f"名称: {asset.name}\n描述: {asset.description or ''}\n内容: {content[:2000] if content else ''}"
    if not _passes_review(review_text):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asset failed AI review. Check description length and sensitive content.")

    tags_list = asset.tags.split(",") if asset.tags else []
    try:
        await index_asset_for_marketplace(
            asset_id=asset.id,
            name=asset.name,
            description=asset.description or "",
            asset_type=type_val,
            tags=tags_list,
        )
    except Exception:
        pass

    asset.visibility = AssetVisibility.PUBLIC.value
    asset.published_version = "1.0.0"
    asset.published_at = datetime.now(timezone.utc)
    await db.flush()

    return _asset_to_out(asset)


@router.post("/{asset_id}/share-team", response_model=AssetOut)
async def share_asset_to_team(
    asset_id: UUID,
    current_user: User = Depends(get_current_user),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    type_val = asset.asset_type.value if hasattr(asset.asset_type, 'value') else str(asset.asset_type)
    content = _read_asset_file(str(asset.space_id), asset.id, type_val)
    tag_list = asset.tags.split(",") if asset.tags else []

    try:
        team_text = f"名称: {asset.name}\n类型: {type_val}\n描述: {asset.description or ''}\n标签: {', '.join(tag_list)}\n内容: {content[:500] if content else ''}"
        metadata = {"asset_id": str(asset.id), "name": asset.name, "asset_type": type_val}
        await embed_and_store(f"team_{str(asset.space_id)}", [team_text], [metadata])
    except Exception:
        pass

    asset.visibility = AssetVisibility.TEAM.value
    await db.flush()

    return _asset_to_out(asset)


@router.get("/team/list", response_model=list[AssetOut])
async def list_team_assets(
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    """List all team members' public/team assets in the current space."""
    actual_space_id = space_id or member.space_id

    result = await db.execute(
        select(Asset).where(
            Asset.space_id == actual_space_id,
            Asset.visibility.in_(["team", "public"]),
        ).order_by(Asset.updated_at.desc())
    )
    assets = result.scalars().all()
    return [_asset_to_out(a) for a in assets]


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


def _write_asset_file(space_id: str, asset_id: UUID, asset_type: str, content: str):
    import os
    type_dirs = {
        "skill": f"skills/{asset_id}",
        "tool": f"tools/{asset_id}",
        "subagent": f"subagents/{asset_id}",
        "mcp": f"mcp/{asset_id}",
        "widget": f"widgets/{asset_id}",
        "pack": f"packs/{asset_id}",
    }
    sub_dir = type_dirs.get(asset_type, f"assets/{asset_id}")
    dir_path = os.path.join("/data/files", space_id, sub_dir)
    os.makedirs(dir_path, exist_ok=True)

    if asset_type == "tool":
        tool_json_path = os.path.join(dir_path, "tool.json")
        main_py_path = os.path.join(dir_path, "main.py")
        try:
            data = json.loads(content) if content else {}
        except json.JSONDecodeError:
            data = {"name": "custom_tool", "description": content}
        with open(tool_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        main_py_content = f'''"""Auto-generated custom tool."""\nimport json\n\ndef execute(**kwargs) -> str:\n    return json.dumps({{"result": "ok", "input": kwargs}}, ensure_ascii=False)\n'''
        with open(main_py_path, "w", encoding="utf-8") as f:
            f.write(main_py_content)
    else:
        file_names = {
            "skill": "SKILL.md",
            "subagent": "agent.md",
            "mcp": "mcp.json",
            "widget": "widget.json",
            "pack": "pack.json",
        }
        file_name = file_names.get(asset_type, "asset.md")
        file_path = os.path.join(dir_path, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)


def _read_asset_file(space_id: str, asset_id: UUID, asset_type: str) -> str:
    import os
    type_dirs = {
        "skill": f"skills/{asset_id}",
        "tool": f"tools/{asset_id}",
        "subagent": f"subagents/{asset_id}",
        "mcp": f"mcp/{asset_id}",
        "widget": f"widgets/{asset_id}",
        "pack": f"packs/{asset_id}",
    }
    file_names = {
        "skill": "SKILL.md",
        "tool": "tool.json",
        "subagent": "agent.md",
        "mcp": "mcp.json",
        "widget": "widget.json",
        "pack": "pack.json",
    }
    sub_dir = type_dirs.get(asset_type, f"assets/{asset_id}")
    file_name = file_names.get(asset_type, "asset.md")
    file_path = os.path.join("/data/files", space_id, sub_dir, file_name)

    if os.path.isfile(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _passes_review(text: str) -> bool:
    if not text or len(text) < 50:
        return False
    sensitive = ["sk-", "api_key", "apikey", "api-key", "secret", "password", "passwd", "token", "Bearer "]
    for p in sensitive:
        if p in text.lower():
            return False
    return True
