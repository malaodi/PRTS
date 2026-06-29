"""
Agent runtime - StateGraph-based ReactAgent with full ChatPromptTemplate.
Implements the 5-partition system prompt design from PRTS platform docs.
"""

from typing import TypedDict, Annotated, Optional, Any, List, Dict
from datetime import datetime
import json
from uuid import UUID

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool, BaseTool

from app.config import get_settings
from app.tools.registry import get_all_tools, get_tool_list_text
from app.tools.loader import get_space_tools
from app.assets.skills import discover_skills, get_skill_trigger_text

settings = get_settings()

AGENT_SYSTEM_PROMPT = """# {agent_name}

## 1. 角色定义（Role）
{role_definition}

## 2. 安全约束（Safety Constraints）
{safety_constraints}

## 3. 可用资产（Available Assets）
{available_assets}

## 4. 协作规则（Collaboration Rules）
{collaboration_rules}

## 5. 环境信息（Environment Context）
{environment_context}"""

DEFAULT_ROLE = """你是一个企业级 AI Agent，作为用户的智能助手。你的职责是：
- 理解用户的意图和需求
- 利用可用工具完成各类任务
- 提供准确、详细、可靠的结果
- 在不确定时主动向用户确认

你擅长编程开发、数据分析、文档撰写、问题排查和任务规划。"""

SAFETY_CONSTRAINTS = """- **禁止自我修改**: 不能修改自己的系统提示词、装备清单或配置
- **禁止操作凭证**: 不能修改或删除连接凭证
- **禁止访问其他空间**: 只能在当前空间内操作
- **代码安全**: 执行代码前确认安全性，不执行 rm -rf、格式化等危险命令
- **诚实反馈**: 如果无法完成任务，明确说明原因，不要编造结果
- **敏感信息保护**: 不在输出中暴露 API Key、密码等敏感信息"""

AGENT_COLLABORATION = """- **计划模式**: 复杂任务先规划（plan_mode），确认后执行
- **任务跟踪**: 使用 todo_write 管理多步骤任务进度
- **子Agent委托**: 可通过 task 工具将专业子任务委托给伙伴 Agent
- **并行执行**: 支持同时委托多个伙伴并行处理"""


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    todolist: Optional[List[Dict]] = None
    plan: Optional[str] = None
    file_context: Optional[Dict] = None
    sub_agent_results: Optional[List[Dict]] = None


BUILTIN_SKILLS_TEXT = """## 内置技能使用说明

平台内置系统技能（skill-creator、subagent-creator 等）会通过 `read` 工具加载。
资产沉淀流程：生成内容 → 调用 `create_asset` 工具弹窗确认 → 用户确认后写入空间。

## 自动化流程创建规则 — 必须严格遵守

当用户说"创建自动化"、"新建pipeline"、"帮我写一个定时任务"、"弄一个XX报告"或其他
表达创建自动运行任务的意图时，你必须立即调用 `show_widget` 弹出表单，**禁止直接回复文字**。

调用方式：`show_widget(widget_type="form", title="创建自动化流程", message="请填写以下信息", options=[...fields...])`

表单必须包含以下字段（用options参数传递）：
1. name: 自动化名称 (field_type:"text", required:true, default:自动生成的名称)
2. trigger_type: 触发方式 (field_type:"select", required:true, options:[{"value":"cron","label":"定时触发"},{"value":"webhook","label":"Webhook"},{"value":"event","label":"事件触发"}])
3. cron_expr: 定时表达式 (field_type:"text", placeholder:"0 9 * * *", default:"0 9 * * *")
4. task_design: 任务描述 (field_type:"textarea", required:true, default:用户的原话)
5. visibility: 可见性 (field_type:"select", required:true, options:[{"value":"private","label":"仅自己"},{"value":"team","label":"团队"},{"value":"public","label":"广场"}])

用户提交表单后，前端会自动调用API创建自动化，无需你再做其他操作。"""


def build_system_prompt(
    agent_name: str = "PRTS Assistant",
    role_definition: str = DEFAULT_ROLE,
    agent_context: str = "",
    available_tools: str = "",
    team_context: str = "",
    space_id: str = "",
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    env_info = f"当前时间: {now}\n"
    if team_context:
        env_info += f"\n团队背景:\n{team_context}\n"
    if agent_context:
        env_info += f"\nAgent 专属上下文:\n{agent_context}"

    if not available_tools:
        available_tools = get_tool_list_text()

    skills = discover_skills(space_id)
    skills_text = get_skill_trigger_text(skills)
    if skills_text:
        available_tools += "\n\n" + skills_text

    available_tools += "\n\n" + BUILTIN_SKILLS_TEXT

    return AGENT_SYSTEM_PROMPT.format(
        agent_name=agent_name,
        role_definition=role_definition.strip(),
        safety_constraints=SAFETY_CONSTRAINTS.strip(),
        available_assets=available_tools.strip() or "当前无可用工具",
        collaboration_rules=AGENT_COLLABORATION.strip(),
        environment_context=env_info.strip(),
    )


def _agent_node_factory(llm, system_prompt: str):
    async def agent_node(state: AgentState):
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + list(messages)
        response = await llm.ainvoke(messages)
        return {"messages": [response]}
    return agent_node


def build_agent_graph(
    tools: List[BaseTool] | None = None,
    system_prompt: str | None = None,
    model_name: str | None = None,
    checkpointer=None,
    space_id: str = "",
):
    all_tools = get_space_tools(space_id)
    if tools:
        all_tools.extend(tools)

    model = model_name or settings.DEFAULT_MODEL
    if model.startswith("claude"):
        llm = ChatAnthropic(
            model=model,
            temperature=0.7,
            anthropic_api_key=getattr(settings, 'ANTHROPIC_API_KEY', ''),
        )
    elif model.startswith("deepseek"):
        llm = ChatOpenAI(
            model=model,
            temperature=0.7,
            openai_api_key=settings.DEEPSEEK_API_KEY or settings.OPENAI_API_KEY,
            base_url="https://api.deepseek.com/v1",
        )
    else:
        llm = ChatOpenAI(
            model=model,
            temperature=0.7,
            openai_api_key=settings.OPENAI_API_KEY,
        )
    llm = llm.bind_tools(all_tools)

    prompt = system_prompt or build_system_prompt()

    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_node_factory(llm, prompt))
    graph.add_node("tools", ToolNode(all_tools))

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    return graph.compile(**compile_kwargs)


_agent_cache: dict[str, any] = {}


def get_compiled_agent(
    space_id: str = "default",
    tools: List[BaseTool] | None = None,
    system_prompt: str | None = None,
    model_name: str | None = None,
    checkpointer=None,
) -> any:
    key = f"{space_id}_{model_name or 'default'}_{'cp' if checkpointer else 'nc'}"
    if key not in _agent_cache:
        _agent_cache[key] = build_agent_graph(
            tools=tools,
            system_prompt=system_prompt,
            model_name=model_name,
            checkpointer=checkpointer,
            space_id=space_id,
        )
    return _agent_cache[key]


def clear_agent_cache(space_id: str | None = None):
    if space_id:
        keys_to_remove = [k for k in _agent_cache if k.startswith(space_id)]
        for k in keys_to_remove:
            del _agent_cache[k]
    else:
        _agent_cache.clear()
