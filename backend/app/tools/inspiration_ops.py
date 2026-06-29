"""
search_inspirations tool — search marketplace and team asset collections in Milvus.
Returns recommendation cards for assets the user doesn't already have.
"""
import json
import asyncio
from langchain_core.tools import tool
from app.tools.vector_ops import vector_search
from app.tools.marketplace_ops import MARKETPLACE_COLLECTION

_current_space_id: str = ""
_current_thread_id: str = ""


def _get_space_id() -> str:
    return _current_space_id or "default"


def _get_thread_id() -> str:
    return _current_thread_id or ""


def set_inspiration_context(space_id: str, thread_id: str = ""):
    global _current_space_id, _current_thread_id
    _current_space_id = space_id
    _current_thread_id = thread_id


@tool
def search_inspirations(
    query: str = "",
    asset_type: str = "",
    source: str = "all",
    top_k: int = 5,
) -> str:
    """搜索市场和团队的资产，获取推荐。用于向用户推荐合适的技能、工具、伙伴等资产。

    当用户在对话中表达"推荐XX相关的资产"、"有没有XX技能"等意图时调用此工具。

    Args:
        query: 搜索关键词，描述需要什么类型的资产
        asset_type: 资产类型过滤 (skill/tool/subagent/mcp/widget/pack)，空表示所有类型
        source: 搜索来源 (marketplace/team/all)，默认all
        top_k: 返回结果数上限，默认5
    """
    space_id = _get_space_id()
    results = []

    if source in ("all", "marketplace"):
        market_hits = _run_search(MARKETPLACE_COLLECTION, query, top_k)
        for hit in market_hits:
            hit["source"] = "marketplace"
            results.append(hit)

    if source in ("all", "team"):
        team_collection = f"team_{space_id}"
        team_hits = _run_search(team_collection, query, top_k)
        for hit in team_hits:
            hit["source"] = "team"
            results.append(hit)

    if asset_type:
        results = [
            r for r in results
            if r.get("metadata", {}).get("asset_type", "") == asset_type
        ]

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    unique = {}
    for r in results:
        name = r.get("metadata", {}).get("name", "")
        if name and name not in unique:
            unique[name] = r
    results = list(unique.values())[:top_k]

    if not results:
        return f"未找到与「{query}」相关的推荐资产。请尝试其他关键词，或告知用户当前市场暂无匹配资产。"

    cards = []
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        cards.append({
            "id": meta.get("asset_id", ""),
            "name": meta.get("name", "未知资产"),
            "asset_type": meta.get("asset_type", ""),
            "source": r.get("source", "marketplace"),
            "score": round(r.get("score", 0), 2),
            "description": r.get("content", "")[:300],
        })

    widget_data = {
        "type": "select",
        "title": f"推荐资产 - 共 {len(cards)} 个匹配结果",
        "message": f"根据「{query}」搜索到以下推荐资产",
        "options": [
            {
                "value": c["id"],
                "label": f"[{c['asset_type']}] {c['name']}",
                "description": f"来源: {c['source']} | 相关度: {c['score']}\n{c.get('description', '')[:100]}",
            }
            for c in cards
        ],
        "multiple": True,
        "_source": "inspiration",
        "_cards": cards,
    }

    return f"[WIDGET:{json.dumps(widget_data, ensure_ascii=False)}]"


def _run_search(collection: str, query: str, top_k: int) -> list:
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(vector_search(collection, query, top_k))
    except RuntimeError:
        return []
    except Exception:
        return []
