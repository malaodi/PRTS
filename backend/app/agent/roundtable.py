"""
Roundtable system - Shared StateGraph multi-agent discussion.
Three modes: moderator, ordered, free.
Maximum 6 participants, 20 rounds. Discussion runs async, conclusion auto-pushed.
"""
from typing import TypedDict, Annotated, Optional, List, Dict
from dataclasses import dataclass, field
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from app.config import get_settings

settings = get_settings()


@dataclass
class RoundtableParticipant:
    agent_id: str
    name: str
    role: str
    perspective: str
    system_prompt: str = ""


class RoundtableState(TypedDict):
    messages: Annotated[list, add_messages]
    topic: str
    current_round: int
    max_rounds: int
    mode: str
    participants: list
    speaker_index: int
    conclusion: Optional[str]
    concluded: bool


def build_roundtable_graph(
    topic: str,
    participants: List[RoundtableParticipant],
    mode: str = "moderator",
    max_rounds: int = 10,
):
    participant_names = [p.name for p in participants]
    llm = ChatOpenAI(
        model=settings.DEFAULT_MODEL,
        temperature=0.7,
        openai_api_key=settings.OPENAI_API_KEY,
    )

    # ── Moderator Prompt ─────────────────────────────────
    moderator_prompt = f"""你是讨论主持人，负责引导一场圆桌讨论。

讨论主题: {topic}

参与者:
{chr(10).join(f'- {p.name} ({p.role}): {p.perspective}' for p in participants)}

你的职责:
1. 根据讨论主题和每位参与者的专长，决定当前轮谁发言
2. 用上一轮的发言内容作为上下文，提出下一个讨论方向
3. 当讨论充分后，总结各方观点并宣布讨论结束

每次输出格式:
**发言人**: [参与者名称]
**讨论方向**: [本轮要讨论的具体问题]
**上一轮摘要**: [简要总结已发表的观点]

如果已经讨论了 {max_rounds} 轮或问题已被充分讨论，输出:
[讨论结束]
**结论**: [汇总共识、分歧和下一步建议]
"""

    # ── Participant Response Function ─────────────────
    async def participant_response(state: RoundtableState, participant: RoundtableParticipant) -> dict:
        context = state["messages"]
        speaker_idx = state.get("speaker_index", 0)

        system_msg = participant.system_prompt or f"""你是 {participant.name}，担任 {participant.role} 角色。
讨论主题: {topic}
你的分析视角: {participant.perspective}
请基于你的专业角度，针对当前讨论方向发表你的看法。保持简洁，2-4 句话。"""

        messages = [SystemMessage(content=system_msg)] + list(context[-6:])
        response = await llm.ainvoke(messages)
        return {"messages": [AIMessage(content=f"**{participant.name}** ({participant.role}):\n{response.content}")]}

    # ── Moderator Mode Graph ──────────────────────────
    def build_moderator_graph():
        graph = StateGraph(RoundtableState)

        async def moderator_node(state: RoundtableState):
            current_round = state.get("current_round", 0) + 1
            if current_round > max_rounds:
                return {"concluded": True, "current_round": current_round}

            messages = [SystemMessage(content=moderator_prompt)]
            for msg in state["messages"][-8:]:
                messages.append(msg)

            messages.append(HumanMessage(
                content=f"当前是第 {current_round}/{max_rounds} 轮。请决定下一个发言人并提出讨论方向。"
            ))
            response = await llm.ainvoke(messages)
            content = str(response.content)

            if "[讨论结束]" in content:
                return {
                    "concluded": True,
                    "conclusion": content,
                    "current_round": current_round,
                    "messages": [response],
                }

            return {
                "current_round": current_round,
                "speaker_index": 0,
                "messages": [response],
            }

        async def speaker_node(state: RoundtableState):
            idx = state.get("speaker_index", 0)
            if idx >= len(participants):
                return {"speaker_index": 0}

            p = participants[idx]
            result = await participant_response(state, p)
            return {
                **result,
                "speaker_index": idx + 1,
            }

        graph.add_node("moderator", moderator_node)
        graph.add_node("speaker", speaker_node)

        graph.add_edge(START, "moderator")

        def route_from_moderator(state: RoundtableState):
            if state.get("concluded"):
                return END
            return "speaker"

        def route_from_speaker(state: RoundtableState):
            idx = state.get("speaker_index", 0)
            if idx >= len(participants):
                return "moderator"
            return "speaker"

        graph.add_conditional_edges("moderator", route_from_moderator, {"speaker": "speaker", END: END})
        graph.add_conditional_edges("speaker", route_from_speaker, {"moderator": "moderator", "speaker": "speaker"})

        return graph.compile(checkpointer=MemorySaver())

    # ── Ordered Mode Graph ────────────────────────────
    def build_ordered_graph():
        graph = StateGraph(RoundtableState)

        async def ordered_speaker(state: RoundtableState):
            current_round = state.get("current_round", 0)
            speaker_idx = state.get("speaker_index", 0)

            if current_round >= max_rounds:
                return {"concluded": True, "current_round": current_round}

            if speaker_idx >= len(participants):
                return {
                    "current_round": current_round + 1,
                    "speaker_index": 0,
                }

            p = participants[speaker_idx]
            result = await participant_response(state, p)
            return {
                **result,
                "speaker_index": speaker_idx + 1,
                "current_round": current_round,
            }

        graph.add_node("ordered_speaker", ordered_speaker)
        graph.add_edge(START, "ordered_speaker")

        def route_ordered(state: RoundtableState):
            if state.get("concluded"):
                return END
            return "ordered_speaker"

        graph.add_conditional_edges("ordered_speaker", route_ordered, {"ordered_speaker": "ordered_speaker", END: END})
        return graph.compile(checkpointer=MemorySaver())

    # ── Free Mode Graph ───────────────────────────────
    def build_free_graph():
        graph = StateGraph(RoundtableState)

        async def free_discussion(state: RoundtableState):
            current_round = state.get("current_round", 0) + 1
            if current_round > max_rounds:
                return {"concluded": True, "current_round": current_round}

            idx = current_round % len(participants)
            p = participants[idx]
            result = await participant_response(state, p)
            return {**result, "current_round": current_round}

        graph.add_node("free_discussion", free_discussion)
        graph.add_edge(START, "free_discussion")

        def route_free(state: RoundtableState):
            if state.get("concluded"):
                return END
            return "free_discussion"

        graph.add_conditional_edges("free_discussion", route_free, {"free_discussion": "free_discussion", END: END})
        return graph.compile(checkpointer=MemorySaver())

    if mode == "ordered":
        return build_ordered_graph()
    elif mode == "free":
        return build_free_graph()
    else:
        return build_moderator_graph()


async def run_roundtable(
    topic: str,
    participants: List[RoundtableParticipant],
    mode: str = "moderator",
    max_rounds: int = 10,
) -> dict:
    """Run a roundtable discussion and return the conclusion."""
    graph = build_roundtable_graph(topic, participants, mode, max_rounds)

    initial_state: RoundtableState = {
        "messages": [HumanMessage(content=f"开始讨论: {topic}")],
        "topic": topic,
        "current_round": 0,
        "max_rounds": max_rounds,
        "mode": mode,
        "participants": [p.__dict__ for p in participants],
        "speaker_index": 0,
        "conclusion": None,
        "concluded": False,
    }

    config = {"configurable": {"thread_id": f"roundtable-{topic[:20]}"}}
    result = await graph.ainvoke(initial_state, config)

    messages = result.get("messages", [])
    conclusion = result.get("conclusion", "")

    if not conclusion and messages:
        conclusion = str(messages[-1].content)[:2000] if messages[-1].content else ""

    transcript = []
    for msg in messages[1:]:
        if msg.content:
            transcript.append(str(msg.content))

    return {
        "conclusion": conclusion or "讨论完成（未生成正式结论）",
        "transcript": transcript,
        "rounds": result.get("current_round", 0),
    }
