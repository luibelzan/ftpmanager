from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from typing import Optional
import os

from app.models.models import Client, DownloadRule, FilePattern, JobExecution, Alert, JobStatus
from app.schemas.schemas import ClientCreate, ClientUpdate
from app.core.config import settings


class ClientService:

    @staticmethod
    async def get_all(db: AsyncSession, active_only: bool = False) -> list[Client]:
        q = select(Client).options(
            selectinload(Client.download_rules).selectinload(DownloadRule.file_patterns)
        ).order_by(Client.name)
        if active_only:
            q = q.where(Client.active == True)
        result = await db.execute(q)
        return result.scalars().all()

    @staticmethod
    async def get_by_id(db: AsyncSession, client_id: str) -> Optional[Client]:
        q = select(Client).options(
            selectinload(Client.download_rules).selectinload(DownloadRule.file_patterns)
        ).where(Client.id == client_id)
        result = await db.execute(q)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> Optional[Client]:
        q = select(Client).where(Client.code == code.upper())
        result = await db.execute(q)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, data: ClientCreate) -> Client:
        os.makedirs(data.local_base_path, exist_ok=True)

        client_data = data.model_dump(exclude={"download_rules"})
        client = Client(**client_data)

        for i, rule_data in enumerate(data.download_rules):
            patterns_data = rule_data.model_dump(exclude={"file_patterns"})
            patterns_data["sort_order"] = i
            rule = DownloadRule(**patterns_data)

            for j, pat_data in enumerate(rule_data.file_patterns):
                valid_fields = {"pattern", "file_type", "local_subfolder", "min_age_days", "min_size_bytes"}
                pat_dict = {k: v for k, v in pat_data.model_dump().items() if k in valid_fields}
                pat = FilePattern(**pat_dict, sort_order=j)
                local_path = os.path.join(data.local_base_path, pat.local_subfolder)
                os.makedirs(local_path, exist_ok=True)
                rule.file_patterns.append(pat)

            client.download_rules.append(rule)

        db.add(client)
        await db.flush()
        await db.refresh(client, ["download_rules"])
        return client

    @staticmethod
    async def update(db: AsyncSession, client_id: str, data: ClientUpdate) -> Optional[Client]:
        client = await ClientService.get_by_id(db, client_id)
        if not client:
            return None

        update_data = data.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(client, field, value)

        client.updated_at = datetime.utcnow()

        if "local_base_path" in update_data:
            os.makedirs(update_data["local_base_path"], exist_ok=True)

        await db.flush()
        return client

    @staticmethod
    async def delete(db: AsyncSession, client_id: str) -> bool:
        result = await db.execute(delete(Client).where(Client.id == client_id))
        return result.rowcount > 0

    @staticmethod
    async def toggle_active(db: AsyncSession, client_id: str) -> Optional[Client]:
        client = await ClientService.get_by_id(db, client_id)
        if not client:
            return None
        client.active = not client.active
        client.updated_at = datetime.utcnow()
        await db.flush()
        return client

    # ─── Download Rules ──────────────────────────────────────────────────────

    @staticmethod
    async def add_rule(db: AsyncSession, client_id: str, rule_data: dict) -> Optional[DownloadRule]:
        client = await ClientService.get_by_id(db, client_id)
        if not client:
            return None

        patterns = rule_data.pop("file_patterns", [])
        rule = DownloadRule(**rule_data, client_id=client_id)

        for j, pat_data in enumerate(patterns):
            # Soportar tanto dicts como objetos Pydantic
            if hasattr(pat_data, "model_dump"):
                pat_dict = pat_data.model_dump(exclude={"sort_order"})
            else:
                pat_dict = {k: v for k, v in pat_data.items() if k != "sort_order"}
            # Campos válidos del modelo FilePattern
            valid_fields = {"rule_id", "pattern", "file_type", "local_subfolder", "min_age_days", "min_size_bytes"}
            pat_dict_clean = {k: v for k, v in pat_dict.items() if k in valid_fields}
            pat = FilePattern(**pat_dict_clean, sort_order=j)
            local_path = os.path.join(client.local_base_path, pat.local_subfolder)
            os.makedirs(local_path, exist_ok=True)
            rule.file_patterns.append(pat)

        db.add(rule)
        await db.flush()
        return rule

    @staticmethod
    async def delete_rule(db: AsyncSession, rule_id: str) -> bool:
        result = await db.execute(delete(DownloadRule).where(DownloadRule.id == rule_id))
        return result.rowcount > 0

    # ─── Stats para dashboard ─────────────────────────────────────────────────

    @staticmethod
    async def get_dashboard_stats(db: AsyncSession) -> dict:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)

        files_today_q = await db.execute(
            select(func.coalesce(func.sum(JobExecution.files_downloaded), 0))
            .where(and_(JobExecution.started_at >= today, JobExecution.status == JobStatus.SUCCESS))
        )
        files_today = files_today_q.scalar()

        files_week_q = await db.execute(
            select(func.coalesce(func.sum(JobExecution.files_downloaded), 0))
            .where(and_(JobExecution.started_at >= week_ago, JobExecution.status == JobStatus.SUCCESS))
        )
        files_week = files_week_q.scalar()

        total_q = await db.execute(select(func.count(Client.id)))
        total = total_q.scalar()

        active_q = await db.execute(select(func.count(Client.id)).where(Client.active == True))
        active = active_q.scalar()

        err_q = await db.execute(
            select(func.count(func.distinct(JobExecution.client_id)))
            .where(and_(
                JobExecution.started_at >= today,
                JobExecution.status == JobStatus.FAILED
            ))
        )
        clients_with_errors = err_q.scalar()

        pending_q = await db.execute(
            select(func.count(Alert.id)).where(Alert.acknowledged == False)
        )
        pending_alerts = pending_q.scalar()

        last_exec_q = await db.execute(
            select(JobExecution).order_by(JobExecution.started_at.desc()).limit(10)
        )
        last_executions = last_exec_q.scalars().all()

        recent_alerts_q = await db.execute(
            select(Alert).order_by(Alert.created_at.desc()).limit(5)
        )
        recent_alerts = recent_alerts_q.scalars().all()

        return {
            "files_today": files_today,
            "files_week": files_week,
            "active_clients": active,
            "total_clients": total,
            "clients_with_errors": clients_with_errors,
            "pending_alerts": pending_alerts,
            "files_by_type_today": {},
            "last_executions": last_executions,
            "recent_alerts": recent_alerts,
        }