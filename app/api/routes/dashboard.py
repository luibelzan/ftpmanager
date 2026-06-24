from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.schemas.schemas import AlertOut, AlertAck, DashboardStats, JobExecutionOut
from app.services.alert_service import AlertService
from app.services.client_service import ClientService
from app.services.scheduler_service import SchedulerService
from app.models.models import JobExecution

# ─── Dashboard ────────────────────────────────────────────────────────────────

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@dashboard_router.get("/stats", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await ClientService.get_dashboard_stats(db)


@dashboard_router.get("/scheduler/jobs")
async def list_scheduler_jobs():
    return SchedulerService.list_jobs()


# ─── Alertas ──────────────────────────────────────────────────────────────────

alerts_router = APIRouter(prefix="/alerts", tags=["Alertas"])


@alerts_router.get("/", response_model=list[AlertOut])
async def list_alerts(
    client_id: str | None = None,
    unack_only: bool = False,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    if unack_only:
        return await AlertService.get_unacknowledged(db)
    return await AlertService.get_all(db, client_id=client_id, limit=limit)


@alerts_router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(alert_id: str, body: AlertAck, db: AsyncSession = Depends(get_db)):
    alert = await AlertService.acknowledge(db, alert_id, by=body.acknowledged_by)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return alert


# ─── Ejecuciones ──────────────────────────────────────────────────────────────

jobs_router = APIRouter(prefix="/jobs", tags=["Ejecuciones"])


@jobs_router.get("/", response_model=list[JobExecutionOut])
async def list_executions(
    client_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    q = select(JobExecution).order_by(JobExecution.started_at.desc()).limit(limit)
    if client_id:
        q = q.where(JobExecution.client_id == client_id)
    result = await db.execute(q)
    return result.scalars().all()


@jobs_router.get("/{job_id}", response_model=JobExecutionOut)
async def get_execution(job_id: str, db: AsyncSession = Depends(get_db)):
    q = select(JobExecution).where(JobExecution.id == job_id)
    result = await db.execute(q)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return job