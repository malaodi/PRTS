"""
Marketplace asset recommendation engine.
Uses Milvus to match user messages against marketplace asset descriptions.
Checks against current space's existing assets to avoid recommending duplicates.
"""
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.models.asset import Asset
from app.tools.vector_ops import vector_search, embed_and_store

MARKETPLACE_COLLECTION = "marketplace_assets"


async def index_asset_for_marketplace(
    asset_id: UUID,
    name: str,
    description: str,
    asset_type: str,
    tags: List[str] = [],
):
    """Index a newly published asset into the marketplace Milvus collection."""
    text = f"名称: {name}\n类型: {asset_type}\n描述: {description}\n标签: {', '.join(tags)}"
    metadata = {"asset_id": str(asset_id), "name": name, "asset_type": asset_type}
    await embed_and_store(MARKETPLACE_COLLECTION, [text], [metadata])


async def recommend_assets(
    user_message: str,
    space_id: UUID,
    db: AsyncSession,
    top_k: int = 5,
    min_score: float = 0.6,
) -> List[Dict]:
    """Recommend marketplace assets based on user message.
    Excludes assets already installed in the current space.
    """
    hits = await vector_search(MARKETPLACE_COLLECTION, user_message, top_k=top_k)

    if not hits:
        return []

    # Get existing asset names in current space
    result = await db.execute(select(Asset.name).where(Asset.space_id == space_id))
    existing_names = set(r[0] for r in result.all())

    recommendations = []
    for hit in hits:
        if hit["score"] < min_score:
            continue
        meta = hit.get("metadata", {})
        name = meta.get("name", "")
        if name and name not in existing_names:
            recommendations.append({
                "asset_id": meta.get("asset_id", ""),
                "name": name,
                "asset_type": meta.get("asset_type", "unknown"),
                "score": round(hit["score"], 2),
                "description": hit.get("content", "")[:200],
            })

    return recommendations[:3]
