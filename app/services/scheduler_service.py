import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.models import Client, DownloadRule

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(
    jobstores={
        "default": SQLAlchemyJobStore(url=settings.DATABASE_URL_SYNC)
    },
    job_defaults={"coalesce": True, "max_instances": 1},
    timezone="Europe/Madrid",
)


async def _run_client_job(client_id: str):
    from app.services.job_runner import JobRunner
    try:
        await JobRunner.run_by_id(client_id, triggered_by="scheduler")
    except Exception as exc:
        logger.error(f"Error en scheduler job para cliente {client_id}: {exc}")


class SchedulerService:

    @staticmethod
    async def load_all_clients():
        from app.db.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            q = (
                select(Client)
                .where(Client.active == True, Client.schedule_active == True)
                .options(selectinload(Client.download_rules).selectinload(DownloadRule.file_patterns))
            )
            result = await db.execute(q)
            clients = result.scalars().all()

        for client in clients:
            if client.schedule_cron:
                SchedulerService.add_or_update(client)

        logger.info(f"Scheduler: {len(clients)} clientes cargados")

    @staticmethod
    def add_or_update(client: Client):
        if not client.schedule_cron:
            return
        job_id = f"client_{client.id}"
        trigger = CronTrigger.from_crontab(client.schedule_cron, timezone="Europe/Madrid")

        if scheduler.get_job(job_id):
            scheduler.reschedule_job(job_id, trigger=trigger)
            logger.info(f"Scheduler: actualizado job para {client.code} ({client.schedule_cron})")
        else:
            scheduler.add_job(
                _run_client_job,
                trigger=trigger,
                id=job_id,
                name=f"FTP {client.code}",
                args=[client.id],
                replace_existing=True,
            )
            logger.info(f"Scheduler: añadido job para {client.code} ({client.schedule_cron})")

    @staticmethod
    def remove(client_id: str):
        job_id = f"client_{client_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"Scheduler: eliminado job {job_id}")

    @staticmethod
    def list_jobs() -> list[dict]:
        jobs = []
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs