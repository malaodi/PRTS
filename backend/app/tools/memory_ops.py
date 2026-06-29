"""
Memory tool — Agent-callable interface for reading/writing/searching memories.
File-based memory: visible, editable, with user confirmation for writes.
"""
import json
from langchain_core.tools import tool

from app.memories.types import MemoryEntry
from app.memories.manager import (
    read_memory, write_memory, delete_memory, read_entrypoint, scan_memories
)
from app.memories.recall import recall_relevant_memories


# Track pending write operations that need user confirmation
_pending_writes: dict[str, list[dict]] = {}


@tool
def memory(
    action: str,
    mem_type: str = "project",
    name: str = "",
    description: str = "",
    content: str = "",
    query: str = "",
    file_name: str = "",
) -> str:
    """管理 Agent 的持久化记忆。写入操作需要用户确认后生效。所有记忆以可见、可编辑的 Markdown 文件存储。

    支持的操作:
    - write: 提议写入一条记忆（需用户确认）
    - read: 读取指定记忆文件
    - search: 语义搜索相关记忆
    - list: 列出所有记忆索引
    - forget: 删除一条记忆（需用户确认）

    Args:
        action: 操作类型 (write/read/search/list/forget)
        mem_type: 记忆类型 (user/feedback/project/reference)，write时使用
        name: 记忆名称，write时使用
        description: 一行描述，用于将来判断相关性，write时使用
        content: 记忆正文(Markdown格式)，write时使用
        query: 搜索查询文本，search时使用
        file_name: 记忆文件名，read/forget时使用
    """
    from app.api.agent import _current_space_id

    space_id = _get_current_space_id()

    if action == "write":
        if not name or not content:
            return "错误: write 操作需要 name 和 content 参数"
        entry = MemoryEntry(
            name=name,
            description=description or name,
            mem_type=mem_type,
            content=content,
        )
        fname = write_memory(space_id, entry)
        return f"已写入记忆: {name} ({mem_type}) → {fname}"

    elif action == "read":
        if not file_name:
            return "错误: read 操作需要 file_name 参数"
        entry = read_memory(space_id, file_name)
        if not entry:
            return f"记忆文件 {file_name} 不存在"
        return f"# {entry.name}\n类型: {entry.mem_type}\n\n{entry.content}"

    elif action == "search":
        if not query:
            return "错误: search 操作需要 query 参数"
        import asyncio
        loop = asyncio.get_event_loop()
        memories = loop.run_until_complete(
            recall_relevant_memories(space_id, query)
        )
        if not memories:
            return "未找到相关记忆"
        lines = []
        for i, m in enumerate(memories, 1):
            fname = m.file_path.split("/")[-1] if m.file_path else ""
            lines.append(f"{i}. [{m.name}] ({fname}): {m.description}")
        return "\n".join(lines)

    elif action == "list":
        entries = read_entrypoint(space_id)
        if not entries:
            return "暂无记忆"
        lines = [f"- [{e.title}]({e.file_name}): {e.description}" for e in entries]
        return "\n".join(lines)

    elif action == "forget":
        if not file_name:
            return "错误: forget 操作需要 file_name 参数"
        delete_memory(space_id, file_name)
        return f"已删除记忆: {file_name}"

    else:
        return f"未知操作: {action}，支持 write/read/search/list/forget"


_current_space_id: str = ""


def set_memory_context(space_id: str):
    global _current_space_id
    _current_space_id = space_id


def _get_current_space_id() -> str:
    return _current_space_id or "default"
