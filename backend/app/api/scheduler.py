"""
API endpoints for managing scheduled scraper jobs.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.services.scheduler import scheduler
from app.services.scraper_jobs import SCRAPER_JOBS

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


class JobConfig(BaseModel):
    job_id: str
    interval_minutes: Optional[int] = None
    enabled: bool = True


class JobStatus(BaseModel):
    id: str
    name: str
    next_run: Optional[str]
    paused: bool
    trigger: str


class JobHistoryEntry(BaseModel):
    timestamp: str
    status: str
    duration: Optional[str] = None
    error: Optional[str] = None


@router.get("/jobs", response_model=List[JobStatus])
async def list_jobs():
    """List all scheduled jobs."""
    return scheduler.get_jobs()


@router.get("/jobs/available")
async def list_available_jobs():
    """List all available scraper jobs that can be scheduled."""
    return {
        job_id: {
            "description": config["description"],
            "default_interval": config["default_interval"],
        }
        for job_id, config in SCRAPER_JOBS.items()
    }


@router.post("/jobs/{job_id}/enable")
async def enable_job(job_id: str, interval_minutes: Optional[int] = None):
    """
    Enable a scraper job.

    Args:
        job_id: The scraper job ID (e.g., 'cardhobby', 'goldin')
        interval_minutes: Override the default interval
    """
    if job_id not in SCRAPER_JOBS:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")

    job_config = SCRAPER_JOBS[job_id]
    interval = interval_minutes or job_config["default_interval"]

    success = scheduler.add_scraper_job(
        job_id=job_id,
        func=job_config["func"],
        interval_minutes=interval,
    )

    if success:
        return {"message": f"Job {job_id} enabled (interval: {interval} minutes)"}
    else:
        raise HTTPException(status_code=500, detail="Failed to enable job")


@router.post("/jobs/{job_id}/disable")
async def disable_job(job_id: str):
    """Disable (remove) a scheduled job."""
    success = scheduler.remove_job(job_id)
    if success:
        return {"message": f"Job {job_id} disabled"}
    else:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    """Pause a scheduled job (keeps schedule but won't run)."""
    success = scheduler.pause_job(job_id)
    if success:
        return {"message": f"Job {job_id} paused"}
    else:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    """Resume a paused job."""
    success = scheduler.resume_job(job_id)
    if success:
        return {"message": f"Job {job_id} resumed"}
    else:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: str, background_tasks: BackgroundTasks):
    """Trigger a job to run immediately (in addition to its schedule)."""
    if job_id not in SCRAPER_JOBS:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")

    # Run in background to not block the response
    job_func = SCRAPER_JOBS[job_id]["func"]
    background_tasks.add_task(job_func)

    return {"message": f"Job {job_id} triggered"}


@router.get("/jobs/{job_id}/history", response_model=List[JobHistoryEntry])
async def get_job_history(job_id: str, limit: int = 20):
    """Get execution history for a job."""
    history = scheduler.get_job_history(job_id, limit=limit)
    return history


@router.get("/status")
async def scheduler_status():
    """Get scheduler status."""
    return {
        "running": scheduler.is_running,
        "job_count": len(scheduler.get_jobs()),
        "jobs": scheduler.get_jobs(),
    }


@router.post("/start")
async def start_scheduler():
    """Start the scheduler (if not already running)."""
    if scheduler.is_running:
        return {"message": "Scheduler already running"}
    scheduler.start()
    return {"message": "Scheduler started"}


@router.post("/stop")
async def stop_scheduler():
    """Stop the scheduler."""
    if not scheduler.is_running:
        return {"message": "Scheduler not running"}
    scheduler.shutdown()
    return {"message": "Scheduler stopped"}
