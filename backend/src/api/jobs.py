"""Background job execution history endpoint."""

from fastapi import APIRouter, Request

from ..services.confirmation_scheduler import trigger_confirmation_now

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/recent")
async def list_recent_jobs(request: Request, job_name: str | None = None, limit: int = 50) -> dict:
    job_repo = request.app.state.job_repo
    runs = await job_repo.list_recent(job_name=job_name, limit=limit)
    return {"runs": runs}


@router.get("/summary")
async def jobs_summary(request: Request) -> dict:
    """Latest run per job — for dashboard."""
    job_repo = request.app.state.job_repo
    summary = await job_repo.latest_by_job()
    return {"jobs": summary}


@router.post("/tplus1/run")
async def run_tplus1_now(request: Request) -> dict:
    """Manually trigger T+1 NAV confirmation immediately (admin/testing)."""
    tx_repo = request.app.state.tx_repo
    counts = await trigger_confirmation_now(tx_repo)
    return {"ok": True, **counts}
