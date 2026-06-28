"""
Plan mode - LangGraph interrupt() based planning system.
Agent generates a plan, pauses for user approval, then executes.
Supports: approve, modify, reject flows.
"""
from typing import TypedDict, Annotated, Optional, List, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from app.config import get_settings

settings = get_settings()


class PlanState(TypedDict):
    messages: Annotated[list, add_messages]
    plan: Optional[str]
    plan_approved: Optional[bool]
    plan_adjustments: Optional[str]


PLAN_MODE_PROMPT = """## 规划模式

你现在处于规划模式。请为用户的请求制定详细的执行计划。

### 计划格式
请在以下结构中组织你的计划：

## 任务概述
一句话描述任务目标

## 预估复杂度
- 步骤数: N 步

## 详细步骤
| 步骤 | 目标 | 方法 | 预期产出 |
|------|------|------|---------|
| 1 | ... | ... | ... |
| 2 | ... | ... | ... |

## 风险点
- [风险]: [缓解措施]

完成后，系统会暂停等待用户确认，确认后才会执行。
请只输出计划，不要开始执行任何操作。"""


def build_plan_mode_graph(
    main_prompt: str,
    tools: List[BaseTool] | None = None,
    model_name: str | None = None,
    checkpointer=None,
):
    all_tools = tools or []
    llm = ChatOpenAI(
        model=model_name or settings.DEFAULT_MODEL,
        temperature=0.5,
        openai_api_key=settings.OPENAI_API_KEY,
    )

    plan_llm = llm.bind_tools([])
    exec_llm = llm.bind_tools(all_tools)

    full_prompt = main_prompt + "\n\n" + PLAN_MODE_PROMPT

    async def plan_node(state: PlanState):
        """Generate a plan and pause for user approval."""
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=full_prompt)] + list(messages)

        response = await plan_llm.ainvoke(messages)
        plan_text = str(response.content)

        decision = interrupt({
            "plan": plan_text,
            "message": "请确认以上执行计划",
            "options": ["approve", "modify", "reject"],
        })

        if isinstance(decision, dict):
            action = decision.get("action", "approve")
            adjustments = decision.get("adjustments", "")
        else:
            action = str(decision) if decision else "approve"
            adjustments = ""

        if action == "reject":
            return {
                "plan": plan_text,
                "plan_approved": False,
                "messages": [response, AIMessage(content="[计划已拒绝，任务取消]")],
            }

        if action == "modify" and adjustments:
            return {
                "plan": plan_text,
                "plan_approved": True,
                "plan_adjustments": adjustments,
                "messages": [
                    response,
                    AIMessage(content=f"[计划已确认，调整: {adjustments}]\n\n现在开始执行..."),
                ],
            }

        return {
            "plan": plan_text,
            "plan_approved": True,
            "messages": [response, AIMessage(content="[计划已确认]\n\n现在开始执行...")],
        }

    async def execution_node(state: PlanState):
        """Execute the approved plan."""
        if not state.get("plan_approved"):
            return {"messages": [AIMessage(content="任务已取消。")]}

        messages = state["messages"]
        adjustments = state.get("plan_adjustments", "")
        if adjustments:
            messages.append(HumanMessage(
                content=f"执行计划时请注意以下调整: {adjustments}\n\n现在请按计划开始执行。"
            ))
        else:
            messages.append(HumanMessage(content="请按计划开始执行。"))

        response = await exec_llm.ainvoke(messages)
        return {"messages": [response]}

    graph = StateGraph(PlanState)

    graph.add_node("plan_node", plan_node)
    graph.add_node("execution_node", execution_node)
    graph.add_node("tool_node", ToolNode(all_tools))

    graph.add_edge(START, "plan_node")
    graph.add_edge("plan_node", "execution_node")

    def after_exec(state: PlanState):
        last_msg = state["messages"][-1] if state["messages"] else None
        if last_msg is None or not hasattr(last_msg, "tool_calls"):
            return END
        if last_msg.tool_calls:
            return "tool_node"
        return END

    graph.add_conditional_edges("execution_node", after_exec, {"tool_node": "tool_node", END: END})
    graph.add_edge("tool_node", "execution_node")

    compile_kwargs = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    return graph.compile(**compile_kwargs)
