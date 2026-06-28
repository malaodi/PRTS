"""
Pipeline scheduler - manages Cron triggers using APScheduler.
Currently active pipelines are scheduled; removes on deactivation.
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

_scheduler: AsyncIOScheduler | None = None
_scheduled_jobs: dict[str, str] = {}


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
        _scheduler.start()
    return _scheduler


def add_pipeline(pipeline_id: str, pipeline) -> None:
    """Add or update a cron trigger for a pipeline."""
    if pipeline.trigger_type.value != "cron":
        return

    config = pipeline.trigger_config or {}
    cron_expr = config.get("expression", "0 9 * * *")

    scheduler = get_scheduler()
    remove_pipeline(pipeline_id)

    try:
        trigger = CronTrigger.from_crontab(cron_expr)
        job = scheduler.add_job(
            _execute_scheduled_pipeline,
            trigger=trigger,
            args=[pipeline_id],
            id=f"pipeline_{pipeline_id}",
            replace_existing=True,
        )
        _scheduled_jobs[pipeline_id] = f"pipeline_{pipeline_id}"
    except Exception:
        pass


def remove_pipeline(pipeline_id: str) -> None:
    """Remove a pipeline's cron trigger."""
    scheduler = get_scheduler()
    job_id = _scheduled_jobs.pop(pipeline_id, None)
    if job_id:
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass


async def _execute_scheduled_pipeline(pipeline_id: str):
    """Execute a scheduled pipeline run."""
    import uuid
    from datetime import datetime, timezone
    from app.database import async_session_factory
    from app.models.pipeline import Pipeline, PipelineRun
    from sqlalchemy import select
    from langchain_core.messages import HumanMessage

    async with async_session_factory() as db:
        try:
            result = await db.execute(
                select(Pipeline).where(Pipeline.id == uuid.UUID(pipeline_id))
            )
            pipeline = result.scalar_one_or_none()
            if not pipeline:
                return

            run = PipelineRun(pipeline_id=pipeline.id, status="running")
            db.add(run)
            await db.commit()

            from app.agent.runtime import get_compiled_agent, build_system_prompt
            from app.agent.checkpointer import get_checkpointer

            system_prompt = build_system_prompt(agent_name=f"{pipeline.name}")
            checkpointer = await get_checkpointer()
            agent_graph = get_compiled_agent(
                space_id=str(pipeline.space_id),
                system_prompt=system_prompt,
                checkpointer=checkpointer,
            )
            config = {"configurable": {"thread_id": f"cron-{pipeline_id}-{run.id}"}}

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
            run.status = "failed"
            run.error_message = str(e)[:2000]
            run.completed_at = datetime.now(timezone.utc)
        finally:
            await db.commit()


class PipelineScheduler:
    """Singleton wrapper for the pipeline scheduler."""

    def add_pipeline(self, pipeline_id: str, pipeline) -> None:
        add_pipeline(pipeline_id, pipeline)

    def remove_pipeline(self, pipeline_id: str) -> None:
        remove_pipeline(pipeline_id)


pipeline_scheduler = PipelineScheduler()
