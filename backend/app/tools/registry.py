"""Tool registry - manages all built-in tools and custom tool registration."""

from typing import List, Dict
from langchain_core.tools import BaseTool

from app.tools.file_ops import read, write, edit, ls, glob_search, grep
from app.tools.code_ops import bash, execute_python
from app.tools.web_ops import web_fetch, web_search, http_request
from app.tools.task_ops import todo_write, task, roundtable, plan_mode
from app.agent.widgets import show_widget as show_widget_tool
from app.tools.document_ops import read_document

BUILTIN_TOOLS: Dict[str, BaseTool] = {
    "read": read,
    "write": write,
    "edit": edit,
    "ls": ls,
    "glob": glob_search,
    "grep": grep,
    "bash": bash,
    "execute_python": execute_python,
    "web_fetch": web_fetch,
    "web_search": web_search,
    "http_request": http_request,
    "todo_write": todo_write,
    "task": task,
    "roundtable": roundtable,
    "plan_mode": plan_mode,
    "show_widget": show_widget_tool,
    "read_document": read_document,
}

TOOL_DESCRIPTIONS: Dict[str, str] = {
    "read": "读取文件内容，支持 offset/limit 分段读取",
    "write": "将内容写入文件",
    "edit": "精确替换文件中的字符串，支持替换全部匹配项",
    "ls": "列出目录中的文件和子目录",
    "glob": "使用 glob 模式搜索匹配的文件",
    "grep": "在文件中搜索匹配正则表达式的行",
    "bash": "执行 Shell/PowerShell 命令，危险命令自动拦截",
    "execute_python": "在隔离环境中执行 Python 代码",
    "web_fetch": "获取网页内容并转换为纯文本",
    "web_search": "搜索互联网获取信息",
    "http_request": "发送 HTTP 请求到指定 URL",
    "todo_write": "管理多步骤任务清单，跟踪复杂任务进度",
    "task": "将子任务委托给伙伴 Agent 执行，单次最多委托一个伙伴",
    "roundtable": "发起多 Agent 圆桌讨论，多个专家共同讨论议题并生成结论",
    "plan_mode": "进入规划模式，先制定执行计划等待确认后再执行",
    "show_widget": "展示交互式卡片（确认/选择/展示/表单）给用户",
    "read_document": "读取并解析文档文件（PDF/CSV/TXT 等）",
}


def get_all_tools() -> List[BaseTool]:
    return list(BUILTIN_TOOLS.values())


def get_tool_by_name(name: str) -> BaseTool | None:
    return BUILTIN_TOOLS.get(name)


def get_tools_by_names(names: List[str]) -> List[BaseTool]:
    return [t for n in names if (t := BUILTIN_TOOLS.get(n)) is not None]


def get_tool_list_text(tool_names: List[str] | None = None) -> str:
    """Generate available tools text for system prompt."""
    if tool_names is None:
        tool_names = list(BUILTIN_TOOLS.keys())

    lines = []
    for name in tool_names:
        if name in BUILTIN_TOOLS and name in TOOL_DESCRIPTIONS:
            lines.append(f"- **{name}**: {TOOL_DESCRIPTIONS[name]}")
    return "\n".join(lines)
