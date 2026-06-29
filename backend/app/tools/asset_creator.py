"""
create_asset tool — Agent generates assets and proposes them to the user.
Uses a pending confirmation pattern: Agent calls tool → stores pending data →
returns confirmation widget → user confirms → frontend calls API to finalize.
"""
import json
import uuid
from langchain_core.tools import tool

_pending_creations: dict[str, dict] = {}
_current_space_id: str = ""
_current_thread_id: str = ""


def _get_space_id() -> str:
    return _current_space_id or "default"


def set_creator_context(space_id: str, thread_id: str = ""):
    global _current_space_id, _current_thread_id
    _current_space_id = space_id
    _current_thread_id = thread_id


def get_pending_creation(thread_id: str) -> dict | None:
    remove_ids = [k for k, v in _pending_creations.items() if v.get("thread_id") == thread_id]
    creation = _pending_creations.get(thread_id)
    for rid in remove_ids:
        _pending_creations.pop(rid, None)
    return creation


@tool
def create_asset(
    asset_type: str,
    name: str,
    description: str = "",
    content: str = "",
    visibility: str = "private",
    tags: str = "",
    config: str = "",
) -> str:
    """从对话中创建资产（技能/工具/伙伴/MCP/卡片/能力套件）。Agent生成资产内容后调用此工具，弹窗让用户确认。

    当Agent想将对话中的知识、代码、角色定义等沉淀为资产时调用。
    用户确认后，资产写入空间并可在设置页查看和装备。

    Args:
        asset_type: 资产类型 (skill/tool/subagent/mcp/widget/pack)
        name: 资产名称，3-30个字符
        description: 资产描述，一行文字说明其功能
        content: 资产核心内容（SKILL.md全文 / tool.json / agent.md / mcp.json / widget配置 / pack.json）
        visibility: 可见性 (private/team/public)，默认private。team=空间成员可见，public=发布到广场
        tags: 标签，逗号分隔，如 "数据分析,财务报表"
        config: 附加配置JSON字符串，如工具的运行参数
    """
    if not asset_type or not name or not content:
        return "错误: create_asset 需要 asset_type、name 和 content 参数"

    valid_types = ("skill", "tool", "subagent", "mcp", "widget", "pack")
    if asset_type not in valid_types:
        return f"错误: asset_type 必须是 {', '.join(valid_types)} 之一"

    valid_vis = ("private", "team", "public")
    if visibility not in valid_vis:
        visibility = "private"

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    creation_id = str(uuid.uuid4())
    _pending_creations[creation_id] = {
        "asset_type": asset_type,
        "name": name,
        "description": description,
        "content": content,
        "visibility": visibility,
        "tags": tag_list,
        "thread_id": _current_thread_id,
        "space_id": _get_space_id(),
    }

    type_labels = {
        "skill": "技能", "tool": "工具", "subagent": "伙伴",
        "mcp": "MCP", "widget": "卡片", "pack": "能力套件",
    }
    vis_labels = {"private": "仅自己", "team": "团队可见", "public": "公开发布"}

    preview = content[:300] + ("..." if len(content) > 300 else "")

    widget_data = {
        "type": "confirm",
        "title": f"保存为{type_labels.get(asset_type, asset_type)}资产",
        "message": (
            f"**名称**: {name}\n"
            f"**类型**: {type_labels.get(asset_type, asset_type)}\n"
            f"**可见性**: {vis_labels.get(visibility, visibility)}\n"
            f"**说明**: {description or '(无)'}\n\n"
            f"**内容预览**:\n```\n{preview}\n```"
        ),
        "confirm_label": "确认创建",
        "cancel_label": "取消",
        "danger": False,
        "_source": "asset_creator",
        "_creation_id": creation_id,
    }

    return f"[WIDGET:{json.dumps(widget_data, ensure_ascii=False)}]"
