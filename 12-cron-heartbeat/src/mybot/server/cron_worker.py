"""server/cron_worker.py -- Background worker that fires cron jobs on schedule."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from mybot.channel.base import EventSource
from mybot.core.context import AppContext
from mybot.core.events import DispatchEvent
from mybot.core.worker import Worker

logger = logging.getLogger(__name__)


def find_due_jobs(jobs, now: datetime | None = None):
    """Return jobs whose cron expression matches the current minute."""
    try:
        from croniter import croniter
    except ImportError:
        logger.warning("croniter not installed -- cron jobs disabled")
        return []
    if now is None:
        now = datetime.now(timezone.utc)
    due = []
    for job in jobs:
        try:
            # Check if this minute falls within the schedule
            cron = croniter(job.schedule, now)
            prev = cron.get_prev(datetime)
            # Due if the last scheduled time is within the past 60 seconds
            delta = (now.replace(tzinfo=None) - prev.replace(tzinfo=None)).total_seconds()
            if 0 <= delta < 60:
                due.append(job)
        except Exception as exc:
            logger.error("Invalid cron expression for job %s: %s", job.id, exc)
    return due


class CronWorker(Worker):
    """Ticks every minute, finds due jobs, publishes DispatchEvents."""

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        # session_id per cron job (one session per cron id)
        self._cron_sessions: dict[str, str] = {}

    async def run(self) -> None:
        logger.info("CronWorker started")
        try:
            while True:
                await self._tick()
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("CronWorker stopping")
            raise

    async def _tick(self) -> None:
        if not self.context.cron_loader:
            return
        jobs = self.context.cron_loader.discover_crons()
        due = find_due_jobs(jobs)
        for job in due:
            await self._dispatch_job(job)

    async def _dispatch_job(self, job) -> None:
        session_id = self._get_or_create_session(job)
        source = EventSource(platform="cron", user_id=job.id, chat_id=job.id)
        event = DispatchEvent(
            session_id=session_id,
            content=job.prompt,
            source=source,
        )
        logger.info("Dispatching cron job %s (session %s)", job.id, session_id)
        await self.context.eventbus.publish(event)
        # Delete one-off jobs after firing
        if job.one_off and self.context.cron_loader:
            self.context.cron_loader.delete_cron(job.id)

    def _get_or_create_session(self, job) -> str:
        if job.id not in self._cron_sessions:
            meta = self.context.history_store.create_session(
                agent_id=job.agent,
                agent_name=job.name,
            )
            self._cron_sessions[job.id] = meta.session_id
        return self._cron_sessions[job.id]
