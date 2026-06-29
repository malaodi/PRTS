"""
Memory recall — selects the top-5 most relevant memory files for a user query.
Uses a lightweight LLM call to compare query against memory descriptions.
Inspired by claude-code's findRelevantMemories using Sonnet side-query.
"""
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import get_settings
from app.memories.types import MemoryEntry, MemoryIndexEntry
from app.memories.manager import read_entrypoint, read_memory

settings = get_settings()

RECALL_SYSTEM_PROMPT = """你是一个记忆召回助手。根据用户的当前查询，从可用记忆列表中选择最多5条最相关的记忆。

返回格式（严格 JSON 数组）:
["file_name_1", "file_name_2", ...]

选择标准:
- 用户当前查询是否与记忆的 description 语义相关
- 优先选择与查询高度相关的记忆
- 如果没有任何相关记忆，返回空数组 []

只返回 JSON 数组，不要其他文字。"""


async def recall_relevant_memories(
    space_id: str,
    user_query: str,
    top_k: int = 5,
) -> List[MemoryEntry]:
    """Select the top-k most relevant memories for a user query."""
    entries = read_entrypoint(space_id)
    if not entries:
        return []

    if len(entries) <= top_k:
        memories = []
        for e in entries:
            entry = read_memory(space_id, e.file_name)
            if entry:
                memories.append(entry)
        return memories

    manifest = "\n".join(
        f"- {e.file_name}: {e.description}" for e in entries
    )

    try:
        llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        messages = [
            SystemMessage(content=RECALL_SYSTEM_PROMPT),
            HumanMessage(content=f"可用记忆:\n{manifest}\n\n用户查询: {user_query}"),
        ]
        response = await llm.ainvoke(messages)

        import json
        try:
            content = str(response.content).strip()
            if content.startswith("```"):
                content = content.split("\n")[1:-1]
                content = "\n".join(content)
            selected = json.loads(content)
        except json.JSONDecodeError:
            selected = [e.file_name for e in entries[:top_k]]

        memories = []
        for fname in selected:
            entry = read_memory(space_id, fname)
            if entry:
                memories.append(entry)
            if len(memories) >= top_k:
                break

        return memories
    except Exception:
        return []
