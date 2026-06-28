"""Automation pipeline API - CRUD, triggers, and execution management."""

import uuid
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.space import SpaceMember
from app.models.pipeline import Pipeline, PipelineRun, PipelineStatus, TriggerType
from app.api.deps import get_current_user, get_current_space_id, require_space_member
from app.pipelines.scheduler import pipeline_scheduler

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class PipelineCreate(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "cron"
    trigger_config: dict | None = None
    task_design: str
    variables_schema: dict | None = None
    max_iterations: int = 50
    timeout_seconds: int = 300


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_config: dict | None = None
    task_design: str | None = None
    status: str | None = None


class PipelineOut(BaseModel):
    id: str
    space_id: str
    name: str
    description: str | None
    trigger_type: str
    trigger_config: dict | None
    task_design: str
    status: str
    created_at: str | None
    last_run_at: str | None

    model_config = {"from_attributes": True}


class PipelineRunOut(BaseModel):
    id: str
    pipeline_id: str
    status: str
    result_summary: str | None
    error_message: str | None
    started_at: str | None
    completed_at: str | None

    model_config = {"from_attributes": True}


def _maybe_val(v: any) -> str:
    return v.value if hasattr(v, 'value') else str(v)


def _pipeline_to_out(p: Pipeline) -> PipelineOut:
    return PipelineOut(
        id=str(p.id),
        space_id=str(p.space_id),
        name=p.name,
        description=p.description,
        trigger_type=_maybe_val(p.trigger_type),
        trigger_config=p.trigger_config,
        task_design=p.task_design,
        status=_maybe_val(p.status),
        created_at=p.created_at.isoformat() if p.created_at else None,
        last_run_at=p.last_run_at.isoformat() if p.last_run_at else None,
    )


def _run_to_out(r: PipelineRun) -> PipelineRunOut:
    return PipelineRunOut(
        id=str(r.id),
        pipeline_id=str(r.pipeline_id),
        status=r.status,
        result_summary=r.result_summary,
        error_message=r.error_message,
        started_at=r.started_at.isoformat() if r.started_at else None,
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
    )


@router.get("", response_model=list[PipelineOut])
async def list_pipelines(
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if space_id:
        conditions.append(Pipeline.space_id == space_id)
        conditions.append(Pipeline.status != PipelineStatus.DELETED)

    result = await db.execute(
        select(Pipeline).where(*conditions).order_by(desc(Pipeline.created_at))
    )
    pipelines = result.scalars().all()
    return [_pipeline_to_out(p) for p in pipelines]


@router.post("", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    data: PipelineCreate,
    current_user: User = Depends(get_current_user),
    space_id: UUID | None = Depends(get_current_space_id),
    member: SpaceMember = Depends(require_space_member),
    db: AsyncSession = Depends(get_db),
):
    actual_space_id = space_id or member.space_id

    pipeline = Pipeline(
        space_id=actual_space_id,
        name=data.name,
        description=data.description,
        trigger_type=TriggerType(data.trigger_type),
        trigger_config=data.trigger_config,
        task_design=data.task_design,
        variables_schema=data.variables_schema,
        max_iterations=data.max_iterations,
        timeout_seconds=data.timeout_seconds,
        created_by=current_user.id,
    )
    db.add(pipeline)
    await db.flush()

    if pipeline.trigger_type == TriggerType.CRON and pipeline.status == PipelineStatus.ACTIVE:
        pipeline_scheduler.add_pipeline(str(pipeline.id), pipeline)

    return _pipeline_to_out(pipeline)


@router.get("/{pipeline_id}", response_model=PipelineOut)
async def get_pipeline(
    pipeline_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    return _pipeline_to_out(pipeline)


@router.patch("/{pipeline_id}", response_model=PipelineOut)
async def update_pipeline(
    pipeline_id: UUID,
    data: PipelineUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")

    if data.name is not None:
        pipeline.name = data.name
    if data.description is not None:
        pipeline.description = data.description
    if data.trigger_config is not None:
        pipeline.trigger_config = data.trigger_config
    if data.task_design is not None:
        pipeline.task_design = data.task_design
    if data.status is not None:
        pipeline.status = PipelineStatus(data.status)

    pipeline_scheduler.remove_pipeline(str(pipeline_id))
    if pipeline.status == PipelineStatus.ACTIVE and pipeline.trigger_type == TriggerType.CRON:
        pipeline_scheduler.add_pipeline(str(pipeline_id), pipeline)

    await db.flush()
    return _pipeline_to_out(pipeline)


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(
    pipeline_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))
    pipeline = result.scalar_one_or_none()
    if pipeline:
        pipeline_scheduler.remove_pipeline(str(pipeline_id))
        pipeline.status = PipelineStatus.DELETED


@router.get("/{pipeline_id}/runs", response_model=list[PipelineRunOut])
async def list_runs(
    pipeline_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.pipeline_id == pipeline_id)
        .order_by(desc(PipelineRun.started_at))
        .limit(50)
    )
    runs = result.scalars().all()
    return [_run_to_out(r) for r in runs]


@router.post("/webhook/{pipeline_id}")
async def trigger_webhook(
    pipeline_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Pipeline).where(
        Pipeline.id == pipeline_id,
        Pipeline.status == PipelineStatus.ACTIVE,
    ))
    pipeline = result.scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found or inactive")

    run = PipelineRun(pipeline_id=pipeline.id, status="running")
    db.add(run)
    await db.flush()

    background_tasks.add_task(execute_pipeline_run, str(pipeline.id), str(run.id))

    return {"status": "triggered", "run_id": str(run.id)}


async def execute_pipeline_run(pipeline_id: str, run_id: str):
    """Execute a pipeline run asynchronously."""
    import asyncio
    from app.database import async_session_factory
    from app.models.pipeline import Pipeline, PipelineRun
    from langchain_core.messages import SystemMessage, HumanMessage

    async with async_session_factory() as db:
        try:
            result = await db.execute(select(Pipeline).where(Pipeline.id == UUID(pipeline_id)))
            pipeline = result.scalar_one_or_none()
            if not pipeline:
                return

            run_result = await db.execute(select(PipelineRun).where(PipelineRun.id == UUID(run_id)))
            run = run_result.scalar_one_or_none()
            if not run:
                return

            from app.agent.runtime import get_compiled_agent, build_system_prompt
            from app.agent.checkpointer import get_checkpointer

            system_prompt = build_system_prompt(
                agent_name=f"{pipeline.name} Pipeline",
            )
            checkpointer = await get_checkpointer()
            agent_graph = get_compiled_agent(
                space_id=str(pipeline.space_id),
                system_prompt=system_prompt,
                checkpointer=checkpointer,
            )
            config = {"configurable": {"thread_id": f"pipeline-{pipeline_id}-{run_id}"}}

            result_state = await agent_graph.ainvoke(
                {"messages": [HumanMessage(content=pipeline.task_design)]},
                config,
            )

            last_msg = result_state.get("messages", [])[-1]
            summary = str(last_msg.content)[:2000] if last_msg.content else "(no output)"

            run.status = "completed"
            run.result_summary = summary
            run.completed_at = datetime.now(timezone.utc)

            pipeline.last_run_at = datetime.now(timezone.utc)

        except Exception as e:
            run_result = await db.execute(select(PipelineRun).where(PipelineRun.id == UUID(run_id)))
            run = run_result.scalar_one_or_none()
            if run:
                run.status = "failed"
                run.error_message = str(e)[:2000]
                run.completed_at = datetime.now(timezone.utc)
        finally:
            await db.commit()
