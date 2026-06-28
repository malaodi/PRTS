"""
Asset-runtime integration bridge.
Queries the DB for agent asset bindings and loads them into the runtime.
Supports the 4-state binding model: enabled / disabled / optional / locked.
"""
from typing import List, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from langchain_core.tools import BaseTool

from app.models.asset import Asset, AgentAssetBinding, AssetType, BindStatus
from app.tools.registry import BUILTIN_TOOLS
from app.tools.loader import discover_custom_tools
from app.tools.mcp import discover_all_mcp_tools
from app.assets.skills import discover_skills, get_skill_trigger_text


async def load_agent_assets(
    db: AsyncSession,
    space_id: UUID,
    agent_id: str,
) -> dict:
    """Load all assets for a specific agent, respecting binding states.

    Returns:
        dict with keys: tools (list), skill_text (str), locked_tool_names (list)
    """
    result = await db.execute(
        select(AgentAssetBinding).where(
            AgentAssetBinding.agent_id == agent_id,
            AgentAssetBinding.status.in_([
                BindStatus.ENABLED,
                BindStatus.LOCKED,
            ]),
        )
    )
    bindings = result.scalars().all()

    custom_tools: List[BaseTool] = []
    skill_assets = []
    enabled_tool_names = list(BUILTIN_TOOLS.keys())

    for binding in bindings:
        asset_result = await db.execute(
            select(Asset).where(Asset.id == binding.asset_id)
        )
        asset = asset_result.scalar_one_or_none()
        if not asset:
            continue

        if asset.asset_type == AssetType.TOOL:
            if binding.status == BindStatus.LOCKED:
                enabled_tool_names.append(asset.name)
        elif asset.asset_type == AssetType.SKILL:
            skill_assets.append(asset)

    # Load filesystem-based custom tools
    fs_tools = discover_custom_tools(str(space_id))
    for name, tool in fs_tools.items():
        if name not in [t.name for t in custom_tools]:
            custom_tools.append(tool)

    tools_list = [BUILTIN_TOOLS[name] for name in enabled_tool_names if name in BUILTIN_TOOLS]
    tools_list.extend(custom_tools)

    skills = discover_skills(str(space_id))
    skill_text = get_skill_trigger_text(skills) if skills else ""

    return {
        "tools": tools_list,
        "skill_text": skill_text,
        "locked_tool_count": len(enabled_tool_names),
    }
