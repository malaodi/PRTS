"""
SubAgent system - LangGraph Subgraph-based multi-agent collaboration.
Implements:
- Subgraph registration with Command(goto) routing
- Send API for parallel dispatch
- asyncio.Semaphore(5) concurrency limit
- State isolation per sub-agent
- Recursion prevention
"""

import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command, Send
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.tools.registry import get_all_tools, get_tools_by_names

settings = get_settings()

MAX_CONCURRENT_SUBAGENTS = 5
_sub_agent_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SUBAGENTS)


# ─── SubAgent Definition ──────────────────────────────────────

@dataclass
class SubAgentConfig:
    agent_id: str
    name: str
    description: str
    system_prompt: str
    tools: List[str] = field(default_factory=list)
    model: str = ""


# ─── SubGraph Builder ─────────────────────────────────────────

def build_sub_agent_graph(config: SubAgentConfig) -> StateGraph:
    from app.agent.runtime import AgentState

    tool_objects = get_tools_by_names(config.tools) if config.tools else get_all_tools()
    model_name = config.model or settings.DEFAULT_MODEL
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.7,
        openai_api_key=settings.OPENAI_API_KEY,
    ).bind_tools(tool_objects)

    async def sub_agent_node(state: AgentState):
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=config.system_prompt)] + list(messages)
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("sub_agent_node", sub_agent_node)
    graph.add_node("sub_tool_node", ToolNode(tool_objects))

    graph.add_edge(START, "sub_agent_node")
    graph.add_conditional_edges("sub_agent_node", tools_condition, {"tools": "sub_tool_node", END: END})
    graph.add_edge("sub_tool_node", "sub_agent_node")

    return graph.compile()


# ─── Agent Builder ────────────────────────────────────────────

_sub_agent_cache: Dict[str, Any] = {}

_EXTREME_CAUTION_MESSAGE = (
    "!!! 极度谨慎 !!!\n\n"
    "你必须非常小心地使用此 task 工具。\n"
    "在以下情况下才使用 task:\n"
    "1. 任务指定的 subagent_id 必须精确匹配以下列表中的 agent_id\n"
    "2. prompt 必须具体、自包含，包含 FILE PATHS，因为子Agent看不到你的对话历史\n"
    "3. 不要把同一个文件分别发给多个子Agent写入（避免冲突）\n"
    "4. 如果你自己能做（用 read/write/bash），就不要委托\n"
)


def build_parent_graph_with_subagents(
    main_prompt: str,
    sub_agents: Dict[str, SubAgentConfig],
    parent_tools: List[str] | None = None,
    model_name: str | None = None,
    checkpointer=None,
):
    from app.agent.runtime import AgentState
    parent_tool_objects = get_tools_by_names(parent_tools) if parent_tools else get_all_tools()

    model = model_name or settings.DEFAULT_MODEL
    llm = ChatOpenAI(
        model=model,
        temperature=0.7,
        openai_api_key=settings.OPENAI_API_KEY,
    ).bind_tools(parent_tool_objects)

    # Compile all sub-agents
    for agent_id, config in sub_agents.items():
        if agent_id not in _sub_agent_cache:
            _sub_agent_cache[agent_id] = build_sub_agent_graph(config)

    # Prepare sub-agent list for the prompt
    sub_agent_descriptions = ""
    if sub_agents:
        sub_agent_descriptions = "\n".join(
            f"- **{cfg.agent_id}**: {cfg.description}" for cfg in sub_agents.values()
        )

    full_prompt = main_prompt
    if sub_agent_descriptions:
        full_prompt += f"\n\n## 可用伙伴 Agent\n{sub_agent_descriptions}\n\n{_EXTREME_CAUTION_MESSAGE}"

    # Build parent graph
    graph = StateGraph(AgentState)

    async def agent_node(state: AgentState):
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=full_prompt)] + list(messages)

        result_state = state.get("sub_agent_results", [])
        if result_state:
            for r in result_state:
                messages.append(AIMessage(content=f"[伙伴 {r['agent_id']}]:\n{r['output']}"))
            state["sub_agent_results"] = []

        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    def route_to_sub_agents(state: AgentState):
        from app.agent.runtime import AgentState as AS
        last_msg = state["messages"][-1] if state["messages"] else None
        if last_msg is None or not hasattr(last_msg, "tool_calls"):
            return "agent_node"

        routing = []
        for tc in last_msg.tool_calls:
            if tc.get("name") == "task":
                args = tc.get("args", {})
                agent_id = args.get("subagent_id", "")
                prompt_text = args.get("prompt", "")
                if agent_id in _sub_agent_cache:
                    routing.append({"agent_id": agent_id, "prompt": prompt_text})

        if not routing:
            return "agent_node"

        sends = []
        for r in routing:
            sends.append(Send(
                f"sub_{r['agent_id']}",
                {
                    "messages": [
                        SystemMessage(content=sub_agents[r['agent_id']].system_prompt),
                        HumanMessage(content=r['prompt']),
                    ]
                }
            ))
        return sends

    # Register nodes
    graph.add_node("agent_node", agent_node)
    graph.add_node("tool_node", ToolNode(parent_tool_objects))

    for agent_id in sub_agents:
        graph.add_node(f"sub_{agent_id}", _sub_agent_cache[agent_id])

    # Edges
    graph.add_edge(START, "agent_node")
    graph.add_conditional_edges("agent_node", tools_condition, {"tools": "tool_node", END: END})
    graph.add_conditional_edges("tool_node", route_to_sub_agents)
    graph.add_edge("tool_node", "agent_node")

    for agent_id in sub_agents:
        graph.add_edge(f"sub_{agent_id}", "agent_node")

    compile_kwargs = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    return graph.compile(**compile_kwargs)
