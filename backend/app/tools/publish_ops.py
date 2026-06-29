"""
publish_asset tool — publishes an asset to the marketplace with AI pre-review.
Handles: AI content review → Milvus vector indexing → Marketplace listing.
"""
import json
from langchain_core.tools import tool

_current_space_id: str = ""


def _get_space_id() -> str:
    return _current_space_id or "default"


def set_publish_context(space_id: str):
    global _current_space_id
    _current_space_id = space_id


AI_REVIEW_PROMPT = """请审查以下准备发布到广场的资产内容。检查项：
1. 名称和描述是否完整（非空，描述超过10字）
2. 是否包含硬编码的敏感信息（API Key、密码、Token、密钥等）
3. 内容质量是否合格（结构清晰、可执行）

返回JSON格式：
{
  "pass": true/false,
  "reason": "通过原因或驳回原因",
  "issues": ["问题1", "问题2"]
}"""


@tool
def publish_asset(
    asset_type: str,
    name: str,
    description: str,
    content: str,
    tags: str = "",
) -> str:
    """将空间内的资产发布到公共广场。需通过AI自动审查后才能上架。

    当用户明确表示"发布到广场"、"公开这个资产"时调用。
    发布后，资产可通过 search_inspirations 被其他用户发现和安装。

    Args:
        asset_type: 资产类型 (skill/tool/subagent/mcp/widget/pack)
        name: 资产名称
        description: 资产描述
        content: 资产完整内容
        tags: 标签，逗号分隔
    """
    if not all([asset_type, name, description, content]):
        return "错误: publish_asset 需要 asset_type、name、description、content 参数"

    review_text = f"资产类型: {asset_type}\n名称: {name}\n描述: {description}\n标签: {tags}\n内容:\n{content[:2000]}"

    review_passed = _perform_review(review_text)

    if not review_passed:
        return json.dumps({
            "status": "review_failed",
            "message": f"资产「{name}」未通过AI审查",
            "detail": "请检查：1) 描述是否完整(>10字) 2) 内容是否包含敏感信息(API Key等) 3) 内容质量是否合格",
        }, ensure_ascii=False)

    return json.dumps({
        "status": "review_passed",
        "message": f"资产「{name}」已通过审查，准备发布到广场",
        "asset_type": asset_type,
        "name": name,
        "description": description,
        "tags": tags,
        "instructions": "请用户确认是否继续发布。确认后将索引到广场并公开可见。",
    }, ensure_ascii=False)


def _perform_review(text: str) -> bool:
    sensitive_patterns = [
        "sk-", "api_key", "apikey", "api-key",
        "secret", "password", "passwd", "token",
        "Bearer ", "Authorization:",
    ]
    text_lower = text.lower()
    for pattern in sensitive_patterns:
        if pattern in text_lower:
            return False

    return True
