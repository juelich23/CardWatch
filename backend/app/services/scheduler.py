"""
Scheduler service for running scrapers on a recurring basis.
Uses APScheduler for job management.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent

logger = logging.getLogger(__name__)


class ScraperScheduler:
    """
    Manages scheduled scraper jobs.

    Usage:
        scheduler = ScraperScheduler()
        scheduler.add_scraper_job("cardhobby", scrape_cardhobby, interval_minutes=30)
        scheduler.start()
    """

    _instance: Optional["ScraperScheduler"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._scheduler = AsyncIOScheduler(
            jobstores={"default": MemoryJobStore()},
            job_defaults={
                "coalesce": True,  # Combine missed runs into one
                "max_instances": 1,  # Only one instance of each job at a time
                "misfire_grace_time": 60 * 5,  # 5 minute grace period
            }
        )
        self._job_history: Dict[str, List[Dict[str, Any]]] = {}
        self._initialized = True

        # Add event listeners
        self._scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self._scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)

    def _on_job_executed(self, event: JobExecutionEvent):
        """Log successful job execution."""
        job_id = event.job_id
        if job_id not in self._job_history:
            self._job_history[job_id] = []

        self._job_history[job_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success",
            "duration": event.scheduled_run_time,
        })

        # Keep only last 100 entries per job
        if len(self._job_history[job_id]) > 100:
            self._job_history[job_id] = self._job_history[job_id][-100:]

        logger.info(f"Job {job_id} executed successfully")

    def _on_job_error(self, event: JobExecutionEvent):
        """Log job errors."""
        job_id = event.job_id
        if job_id not in self._job_history:
            self._job_history[job_id] = []

        self._job_history[job_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "status": "error",
            "error": str(event.exception) if event.exception else "Unknown error",
        })

        logger.error(f"Job {job_id} failed: {event.exception}")

    def add_scraper_job(
        self,
        job_id: str,
        func: Callable,
        interval_minutes: int = 30,
        start_immediately: bool = False,
        **kwargs
    ) -> bool:
        """
        Add a scraper job to run at a fixed interval.

        Args:
            job_id: Unique identifier for the job
            func: Async function to run
            interval_minutes: How often to run (default 30 minutes)
            start_immediately: Whether to run immediately on startup
            **kwargs: Additional arguments to pass to the function

        Returns:
            True if job was added successfully
        """
        try:
            # Remove existing job if present
            if self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)

            trigger = IntervalTrigger(minutes=interval_minutes)

            self._scheduler.add_job(
                func,
                trigger=trigger,
                id=job_id,
                name=f"Scraper: {job_id}",
                kwargs=kwargs,
                replace_existing=True,
            )

            logger.info(f"Added job {job_id} to run every {interval_minutes} minutes")

            # Optionally run immediately
            if start_immediately and self._scheduler.running:
                asyncio.create_task(func(**kwargs))

            return True

        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {e}")
            return False

    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        cron_expression: str = "*/30 * * * *",
        **kwargs
    ) -> bool:
        """
        Add a job with cron-style scheduling.

        Args:
            job_id: Unique identifier for the job
            func: Async function to run
            cron_expression: Cron expression (default: every 30 minutes)
            **kwargs: Additional arguments to pass to the function
        """
        try:
            if self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)

            # Parse cron expression
            parts = cron_expression.split()
            trigger = CronTrigger(
                minute=parts[0] if len(parts) > 0 else "*",
                hour=parts[1] if len(parts) > 1 else "*",
                day=parts[2] if len(parts) > 2 else "*",
                month=parts[3] if len(parts) > 3 else "*",
                day_of_week=parts[4] if len(parts) > 4 else "*",
            )

            self._scheduler.add_job(
                func,
                trigger=trigger,
                id=job_id,
                name=f"Scraper: {job_id}",
                kwargs=kwargs,
                replace_existing=True,
            )

            logger.info(f"Added cron job {job_id}: {cron_expression}")
            return True

        except Exception as e:
            logger.error(f"Failed to add cron job {job_id}: {e}")
            return False

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job."""
        try:
            if self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)
                logger.info(f"Removed job {job_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False

    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job."""
        try:
            self._scheduler.pause_job(job_id)
            logger.info(f"Paused job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        try:
            self._scheduler.resume_job(job_id)
            logger.info(f"Resumed job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            return False

    def run_job_now(self, job_id: str) -> bool:
        """Trigger a job to run immediately."""
        try:
            job = self._scheduler.get_job(job_id)
            if job:
                # Run the job function directly
                asyncio.create_task(job.func(**job.kwargs))
                logger.info(f"Triggered immediate run of job {job_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to run job {job_id}: {e}")
            return False

    def get_jobs(self) -> List[Dict[str, Any]]:
        """Get list of all scheduled jobs."""
        jobs = []
        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
                "paused": next_run is None,
                "trigger": str(job.trigger),
            })
        return jobs

    def get_job_history(self, job_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get execution history for a job."""
        history = self._job_history.get(job_id, [])
        return history[-limit:]

    def start(self):
        """Start the scheduler."""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Scheduler started")

    def shutdown(self):
        """Shutdown the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("Scheduler shutdown")

    @property
    def is_running(self) -> bool:
        return self._scheduler.running


# Global scheduler instance
scheduler = ScraperScheduler()
