"""Task management and planning tools."""

from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.tools import tool


TodoStatus = Literal["pending", "in_progress", "completed", "cancelled"]


class TodoItem(BaseModel):
    id: str = Field(description="任务唯一标识")
    content: str = Field(description="任务描述")
    status: TodoStatus = Field(description="任务状态")


@tool
def todo_write(
    todos: List[TodoItem],
    merge: bool = True,
) -> str:
    """管理多步骤任务列表。用于跟踪复杂任务的进度。

    Args:
        todos: 任务列表，每个任务包含 id、content 和 status
        merge: 是否合并到现有列表（True=追加/更新，False=替换）
    """
    status_icons = {
        "pending": "⬜",
        "in_progress": "🔄",
        "completed": "✅",
        "cancelled": "❌",
    }
    lines = []
    for t in todos:
        icon = status_icons.get(t.status, "❓")
        lines.append(f"{icon} [{t.id}] {t.content}")

    mode = "合并更新" if merge else "替换列表"
    return f"任务清单 ({mode}):\n" + "\n".join(lines)


# Stub for task delegation (will be expanded in Stage 4)
@tool
def task(
    subagent_id: str,
    prompt: str,
    run_in_background: bool = False,
) -> str:
    """将子任务委托给伙伴 Agent 执行。

    Args:
        subagent_id: 伙伴 Agent 的标识符
        prompt: 发送给伙伴的任务描述
        run_in_background: 是否后台运行（不等待结果）
    """
    if run_in_background:
        return f"[后台任务] 已委托给 {subagent_id}，不等待结果。"
    return f"[委托任务] 已发送给 {subagent_id}。提示: '{prompt[:200]}...' (子Agent系统正在初始化中)"
