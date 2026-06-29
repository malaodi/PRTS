"""
Memory extraction — post-conversation background agent that evaluates whether to write/update memories.
Forked agent pattern inspired by claude-code's extractMemories.
"""
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.config import get_settings
from app.memories.types import MemoryEntry
from app.memories.manager import read_entrypoint, read_memory, write_memory
from app.memories.recall import recall_relevant_memories

settings = get_settings()

EXTRACT_PROMPT = """你是一个记忆提取助手。分析对话内容，判断是否有值得保存的记忆。

值得保存的记忆类型:
- **user**: 用户的角色、偏好、背景信息
- **feedback**: 用户对Agent的纠正或肯定反馈
- **project**: 项目上下文、截止日期、重要决策
- **reference**: 外部系统、文档、工具的引用说明

不需要保存的内容:
- 代码实现细节（可从代码库推导）
- 一次性问答
- 已经在某条已有记忆中覆盖的内容

返回格式（严格 JSON，如果不需要写入记忆则返回 null）:
{
  "should_write": true/false,
  "type": "user|feedback|project|reference",
  "name": "记忆名称（简洁）",
  "description": "一行描述（用于将来判断相关性）",
  "content": "记忆正文（Markdown格式）",
  "update_existing": "如果更新已有记忆，填目标文件名，否则null"
}

只返回 JSON，不要其他文字。"""


async def evaluate_extraction(
    space_id: str,
    user_message: str,
    assistant_response: str,
) -> dict | None:
    """Evaluate whether a conversation turn should produce a memory."""
    entries = read_entrypoint(space_id)
    existing_manifest = ""
    if entries:
        existing_manifest = "已有记忆:\n" + "\n".join(
            f"- {e.file_name}: {e.description}" for e in entries
        )

    try:
        llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        messages = [
            SystemMessage(content=EXTRACT_PROMPT),
            HumanMessage(content=f"""{existing_manifest}

用户消息: {user_message}

Agent回复（摘要）: {assistant_response[:2000]}
"""),
        ]
        response = await llm.ainvoke(messages)

        import json
        content = str(response.content).strip()
        if content.startswith("```"):
            content = content.split("\n")[1:-1]
            content = "\n".join(content)
        result = json.loads(content)

        if not isinstance(result, dict) or not result.get("should_write"):
            return None

        return result
    except Exception:
        return None


async def apply_extraction(space_id: str, extraction: dict):
    """Apply a memory extraction result — write or update a memory file."""
    mem_type = extraction.get("type", "project")
    name = extraction.get("name", "")
    description = extraction.get("description", "")
    content = extraction.get("content", "")
    update_existing = extraction.get("update_existing")

    if update_existing:
        existing = read_memory(space_id, update_existing)
        if existing:
            existing.content = content
            existing.updated = ""
            write_memory(space_id, existing)
            return update_existing

    entry = MemoryEntry(
        name=name,
        description=description,
        mem_type=mem_type,
        content=content,
    )
    return write_memory(space_id, entry)
