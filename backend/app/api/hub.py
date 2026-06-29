"""Hub marketplace API endpoints — publish/pull/feedback with Milvus indexing."""

from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.space import SpaceMember
from app.models.asset import Asset, AssetType, AssetVisibility
from app.api.deps import get_current_user, get_current_space_id, require_space_member
from app.hub import hub_pull, hub_push, record_feedback
from app.tools.marketplace_ops import index_asset_for_marketplace

router = APIRouter(prefix="/hub", tags=["hub"])


def _tval(a: Asset) -> str:
    return a.asset_type.value if hasattr(a.asset_type, 'value') else str(a.asset_type)


class PullRequest(BaseModel):
    namespace: str
    asset_type: str = "prompt"


class PushRequest(BaseModel):
    asset_id: str
    namespace: str = ""
    description: str = ""


class FeedbackRequest(BaseModel):
    run_id: str
    score: float
    comment: str = ""


@router.post("/pull")
async def pull_from_hub(data: PullRequest, _=Depends(get_current_user)):
    result = hub_pull(data.namespace, data.asset_type)
    if result is None:
        raise HTTPException(status_code=404, detail="Asset not found on Hub")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "ok", "namespace": data.namespace, "type": data.asset_type}


@router.post("/push")
async def push_to_hub(
    data: PushRequest,
    current_user: User = Depends(get_current_user),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    asset_id = UUID(data.asset_id)
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    content_text = f"名称: {asset.name}\n类型: {_tval(asset)}\n描述: {asset.description or ''}"
    if not _passes_review(content_text):
        raise HTTPException(status_code=400, detail="Asset failed AI review. Ensure description >=10 chars and no hardcoded secrets.")

    tags_list = asset.tags.split(",") if asset.tags else []
    try:
        await index_asset_for_marketplace(
            asset_id=asset.id,
            name=asset.name,
            description=asset.description or "",
            asset_type=_tval(asset),
            tags=tags_list,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Milvus indexing failed: {str(e)}")

    asset.visibility = AssetVisibility.PUBLIC.value
    asset.published_version = "1.0.0"
    asset.published_at = datetime.now(timezone.utc)
    await db.flush()

    # LangSmith Hub push (best-effort)
    hub_push(data.namespace or asset.name, None, description=data.description)

    return {
        "status": "published",
        "asset_id": str(asset.id),
        "namespace": data.namespace or asset.name,
        "visibility": asset.visibility,
    }


@router.post("/feedback")
async def submit_feedback(data: FeedbackRequest, _=Depends(get_current_user)):
    success = record_feedback(data.run_id, data.score, data.comment)
    return {"status": "ok" if success else "error", "message": "Feedback recorded" if success else "Hub not configured"}


@router.get("/explore")
async def explore_marketplace(
    asset_type: str | None = Query(None),
    query: str | None = Query(None),
    top_k: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    conditions = [Asset.visibility == AssetVisibility.PUBLIC.value]
    if asset_type:
        conditions.append(Asset.asset_type == asset_type)

    result = await db.execute(
        select(Asset).where(*conditions).order_by(Asset.published_at.desc()).limit(top_k)
    )
    assets = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "space_id": str(a.space_id),
            "asset_type": _tval(a),
            "name": a.name,
            "description": a.description,
            "tags": a.tags.split(",") if a.tags else [],
            "published_version": a.published_version,
            "published_at": a.published_at.isoformat() if a.published_at else None,
        }
        for a in assets
    ]


@router.get("/my-publications")
async def my_publications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Asset).where(
            Asset.created_by == current_user.id,
            Asset.visibility == AssetVisibility.PUBLIC.value,
        ).order_by(Asset.published_at.desc())
    )
    assets = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "asset_type": _tval(a),
            "name": a.name,
            "description": a.description,
            "tags": a.tags.split(",") if a.tags else [],
            "published_version": a.published_version,
            "published_at": a.published_at.isoformat() if a.published_at else None,
        }
        for a in assets
    ]


def _passes_review(text: str) -> bool:
    if not text or len(text) < 50:
        return False
    sensitive = ["sk-", "api_key", "apikey", "api-key", "secret", "password", "passwd", "token", "Bearer "]
    for p in sensitive:
        if p in text.lower():
            return False
    return True
