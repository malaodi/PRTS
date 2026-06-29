import json
import os
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.session import Session
from app.models.space import Space, SpaceMember
from app.models.user import User
from app.models.agent_config import Agent
from app.api.deps import get_current_user, get_current_space_id, require_space_member
from app.agent.runtime import get_compiled_agent, build_system_prompt, AgentState
from app.agent.checkpointer import get_checkpointer
from app.credentials.injector import load_credentials, inject_into_env, clear_from_env
from app.files.workspace import get_workspace
from app.assets.loader import load_agent_assets
from app.memories.recall import recall_relevant_memories
from app.memories.extract import evaluate_extraction, apply_extraction
from app.memories.manager import read_memory, read_entrypoint
from app.config import get_settings
from app.tools.memory_ops import set_memory_context
from app.tools.inspiration_ops import set_inspiration_context
from app.tools.asset_creator import set_creator_context
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None
    model: str | None = None
    agent_id: str | None = None


class SessionOut(BaseModel):
    id: str
    thread_id: str
    title: str | None
    created_at: str | None

    model_config = {"from_attributes": True}


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    db: AsyncSession = Depends(get_db),
):
    conditions = [Session.user_id == current_user.id]
    if space_id:
        conditions.append(Session.space_id == space_id)

    result = await db.execute(
        select(Session)
        .where(*conditions)
        .order_by(desc(Session.updated_at))
        .limit(50)
    )
    sessions = result.scalars().all()
    return [
        SessionOut(
            id=str(s.id),
            thread_id=s.thread_id,
            title=s.title,
            created_at=s.created_at.isoformat() if s.created_at else None,
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)


class MessageOut(BaseModel):
    role: str
    content: str


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_session_messages(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return await _load_thread_messages(session.thread_id)


@router.get("/messages", response_model=list[MessageOut])
async def get_thread_messages(
    thread_id: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    return await _load_thread_messages(thread_id)


async def _load_thread_messages(thread_id: str) -> list[dict]:
    """Load historical messages for a thread from the LangGraph checkpointer."""
    try:
        from app.agent.checkpointer import get_checkpointer
        cp = await get_checkpointer()
        config = {"configurable": {"thread_id": thread_id}}
        state = await cp.aget_tuple(config)
        if not state or not state.checkpoint:
            return []

        channel_values = state.checkpoint.get("channel_values", {})
        raw_messages = channel_values.get("messages", [])

        out = []
        for m in raw_messages:
            role = getattr(m, 'type', None) or getattr(m, 'role', None)
            if role == 'human':
                role = 'user'
            elif role == 'ai':
                role = 'assistant'
            elif role == 'tool':
                continue
            elif role == 'system':
                continue
            content = getattr(m, 'content', '') or ''
            if isinstance(content, list):
                content = ''.join(str(c) for c in content if isinstance(c, str))
            out.append({"role": role or 'assistant', "content": str(content)})
        return out
    except Exception:
        return []


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    actual_space_id = space_id or member.space_id

    team_context = ""
    space_name = "PRTS"
    if actual_space_id:
        space_result = await db.execute(select(Space).where(Space.id == actual_space_id))
        space = space_result.scalar_one_or_none()
        if space:
            team_context = space.team_context or ""
            space_name = space.name

    thread_id = request.thread_id
    if not thread_id:
        session = Session(
            space_id=actual_space_id,
            user_id=current_user.id,
            thread_id="",
            title=request.message[:100] if request.message else "New Chat",
        )
        db.add(session)
        await db.flush()
        thread_id = f"space-{actual_space_id}-session-{session.id}"
        session.thread_id = thread_id

    model_name = request.model
    agent_name = f"{space_name} Assistant"
    custom_prompt = None

    if request.agent_id:
        try:
            agent_result = await db.execute(
                select(Agent).where(Agent.id == UUID(request.agent_id))
            )
            agent = agent_result.scalar_one_or_none()
            if agent:
                agent_name = agent.name
                if not model_name:
                    model_name = agent.model
                custom_prompt = agent.get_prompt_content()
        except ValueError:
            pass

    if not model_name:
        settings = get_settings()
        model_name = settings.DEFAULT_MODEL

    space_id_str = str(actual_space_id or "")
    set_memory_context(space_id_str)
    set_inspiration_context(space_id_str, thread_id)
    set_creator_context(space_id_str, thread_id)

    system_prompt = build_system_prompt(
        agent_name=agent_name,
        team_context=team_context,
        space_id=str(actual_space_id or ""),
    )

    if custom_prompt:
        system_prompt = custom_prompt

    # Inject relevant memories into system prompt
    memories = await recall_relevant_memories(str(actual_space_id or ""), request.message)
    if memories:
        memory_lines = ["\n\n## 🧠 相关记忆\n"]
        for i, m in enumerate(memories, 1):
            fname = m.file_path.split("/")[-1] if m.file_path else ""
            memory_lines.append(f"### {i}. {m.name}\n{m.content.strip()[:1000]}\n")
        system_prompt += "".join(memory_lines)

    # Pipeline creation interceptor: detect keywords → LLM generates custom form widget
    import re
    pipeline_keywords = ["创建自动化", "创建管道", "创建pipeline", "定时任务", "自动化流程",
                         "新建自动化", "帮我自动化", "做一个自动化", "搞一个自动化",
                         "定时推送", "定时抓取", "定时执行", "定时发送",
                         "竞品调研", "报告生成", "监控"]
    msg_lower = request.message.lower()
    is_pipeline_intent = any(kw.lower() in msg_lower for kw in pipeline_keywords) or \
                         bool(re.search(r"每天.*点", msg_lower)) or \
                         bool(re.search(r"每周.*点", msg_lower))

    if is_pipeline_intent and not request.thread_id:
        async def pipeline_form_stream():
            try:
                yield f"data: {json.dumps({'type': 'metadata', 'thread_id': thread_id})}\n\n"
                yield f"data: {json.dumps({'content': '好的，让我来分析你的需求，生成一份定制化的表单…\\n\\n'})}\n\n"

                # Call LLM to generate custom form
                form_widget = await _generate_pipeline_form(request.message)

                yield f"data: {json.dumps({'content': '[WIDGET:' + json.dumps(form_widget, ensure_ascii=False) + ']'})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            pipeline_form_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    checkpointer = await get_checkpointer()

    cred_ctx = await load_credentials(db, actual_space_id, current_user.id)
    inject_into_env(cred_ctx)

    session_id = thread_id
    workspace = get_workspace(actual_space_id, thread_id)
    os_env = workspace.get_env_vars()
    for k, v in os_env.items():
        os.environ[k] = v

    agent_graph = get_compiled_agent(
        space_id=str(actual_space_id or "default"),
        system_prompt=system_prompt,
        model_name=model_name,
        checkpointer=checkpointer,
    )

    if request.agent_id:
        assets = await load_agent_assets(db, actual_space_id, str(request.agent_id))
        if assets.get("skill_text") and not custom_prompt:
            system_prompt += "\n\n" + assets["skill_text"]
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: AgentState = {
        "messages": [HumanMessage(content=request.message)],
    }

    async def event_stream():
        assistant_content = []
        try:
            yield f"data: {json.dumps({'type': 'metadata', 'thread_id': thread_id})}\n\n"
            async for event in agent_graph.astream_events(initial_state, config, version="v2"):
                kind = event.get("event", "")
                if kind == "on_chat_model_stream":
                    data = event.get("data", {})
                    chunk = data.get("chunk", None)
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        assistant_content.append(chunk.content)
                        yield f"data: {json.dumps({'content': chunk.content})}\n\n"
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    yield f"data: {json.dumps({'type': 'tool_start', 'name': tool_name})}\n\n"
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    yield f"data: {json.dumps({'type': 'tool_end', 'name': tool_name})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            clear_from_env(cred_ctx)
            # Post-turn memory extraction
            try:
                full_response = "".join(assistant_content)
                if len(full_response) > 100:
                    extraction = await evaluate_extraction(
                        str(actual_space_id or ""),
                        request.message,
                        full_response,
                    )
                    if extraction:
                        await apply_extraction(str(actual_space_id or ""), extraction)
            except Exception:
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


PIPELINE_FORM_PROMPT = """You are a form generator. Given a user's request to create an automation, generate a form widget JSON.

The user said: '{user_message}'

Based on their request, create a form to collect all needed information. The form must be in this exact JSON format:
{{
  "type": "form",
  "title": "简短的表单标题",
  "message": "一行提示消息",
  "fields": [
    {{"key":"name","label":"自动化名称","field_type":"text","required":true,"default":"自动推断的名称"}},
    {{"key":"trigger_type","label":"触发方式","field_type":"select","required":true,"options":[{{"value":"cron","label":"定时"}},{{"value":"webhook","label":"Webhook"}}]}},
    {{"key":"cron_expr","label":"时间表达式","field_type":"text","placeholder":"0 9 * * *","default":"推断的时间"}},
    {{"key":"task_design","label":"任务描述","field_type":"textarea","required":true,"default":"用户原话摘要"}},
    {{"key":"visibility","label":"可见性","field_type":"select","required":true,"options":[{{"value":"private","label":"仅自己"}},{{"value":"team","label":"团队"}},{{"value":"public","label":"广场"}}]}}
  ]
}}

Rules:
- Infer a good name from the user's request. Keep it short (3-15 chars).
- If the user mentions a time (e.g. "每天8点"), infer the cron expression. cron format: "分 时 日 月 周". "每天8点" = "0 8 * * *".
- If user mentions a specific platform/tool (e.g. 企微/飞书/GitHub/Slack/邮件), add an extra field about it (e.g. channel selection).
- If user mentions specific data sources or keywords, add relevant fields.
- Only use field_types: text, textarea, select. No other types.
- All fields MUST have a 'key' (english, snake_case), 'label' (Chinese), and 'field_type'.
- Return ONLY the JSON object. No markdown, no explanation, no code fences."""


async def _generate_pipeline_form(user_message: str) -> dict:
    """Call LLM to generate a customized pipeline form widget based on user's message."""
    from app.config import get_settings
    cfg = get_settings()

    api_key = cfg.OPENAI_API_KEY or cfg.DEEPSEEK_API_KEY
    if not api_key:
        return _fallback_form(user_message)

    prompt = PIPELINE_FORM_PROMPT.replace("{user_message}", user_message).replace("{{", "{").replace("}}", "}")

    try:
        if cfg.DEEPSEEK_API_KEY and not cfg.OPENAI_API_KEY:
            llm = ChatOpenAI(model="deepseek-chat", temperature=0.1, openai_api_key=cfg.DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")
        else:
            llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.1, openai_api_key=cfg.OPENAI_API_KEY)

        response = await llm.ainvoke(prompt)
        content = str(response.content).strip()

        # Strip code fences if present
        if content.startswith("```"):
            content = "\n".join(content.split("\n")[1:])
        if content.endswith("```"):
            content = content[:-3].strip()

        result = json.loads(content)
        if result.get("type") == "form" and result.get("fields"):
            return result
    except Exception:
        pass

    return _fallback_form(user_message)


def _fallback_form(user_message: str) -> dict:
    """Hardcoded fallback form when LLM fails."""
    name = user_message[:20].replace(" ", "")
    return {
        "type": "form",
        "title": "创建自动化流程",
        "message": "请填写以下信息",
        "fields": [
            {"key": "name", "label": "自动化名称", "field_type": "text", "required": True, "default": name},
            {"key": "trigger_type", "label": "触发方式", "field_type": "select", "required": True,
             "options": [{"value": "cron", "label": "定时"}, {"value": "webhook", "label": "Webhook"}]},
            {"key": "cron_expr", "label": "定时表达式", "field_type": "text", "placeholder": "0 9 * * *", "default": "0 9 * * *"},
            {"key": "task_design", "label": "任务描述", "field_type": "textarea", "required": True, "default": user_message},
            {"key": "visibility", "label": "可见性", "field_type": "select", "required": True,
             "options": [{"value": "private", "label": "仅自己"}, {"value": "team", "label": "团队"}, {"value": "public", "label": "广场"}]},
        ],
    }
