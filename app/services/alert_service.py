import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Alert, AlertLevel, AlertType, Client
from app.core.config import settings

logger = logging.getLogger(__name__)


class AlertService:

    @staticmethod
    async def create(
        db: AsyncSession,
        alert_type: AlertType,
        level: AlertLevel,
        message: str,
        client: Optional[Client] = None,
        job_execution_id: Optional[str] = None,
    ) -> Alert:
        alert = Alert(
            alert_type=alert_type,
            level=level,
            message=message,
            client_id=client.id if client else None,
            job_execution_id=job_execution_id,
        )
        db.add(alert)
        await db.flush()

        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            sent = await AlertService._send_telegram(alert, client)
            if sent:
                alert.notified_telegram = True

        logger.warning(f"[ALERTA:{level}] {alert_type} — {message}")
        return alert

    @staticmethod
    async def acknowledge(
        db: AsyncSession,
        alert_id: str,
        by: str,
    ) -> Optional[Alert]:
        q = select(Alert).where(Alert.id == alert_id)
        result = await db.execute(q)
        alert = result.scalar_one_or_none()
        if not alert:
            return None
        alert.acknowledged = True
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = by
        await db.flush()
        return alert

    @staticmethod
    async def get_unacknowledged(db: AsyncSession) -> list[Alert]:
        q = select(Alert).where(Alert.acknowledged == False).order_by(Alert.created_at.desc())
        result = await db.execute(q)
        return result.scalars().all()

    @staticmethod
    async def get_all(
        db: AsyncSession,
        client_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[Alert]:
        q = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        if client_id:
            q = q.where(Alert.client_id == client_id)
        result = await db.execute(q)
        return result.scalars().all()

    # ─── Telegram ─────────────────────────────────────────────────────────────

    @staticmethod
    async def _send_telegram(alert: Alert, client: Optional[Client]) -> bool:
        try:
            import httpx
            level_emoji = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🟢"}.get(alert.level, "⚪")
            client_name = client.name if client else "Sistema"
            text = (
                f"{level_emoji} *FTP Manager — {alert.level}*\n"
                f"Cliente: `{client_name}`\n"
                f"Tipo: `{alert.alert_type}`\n"
                f"Mensaje: {alert.message}\n"
                f"Hora: {alert.created_at.strftime('%d/%m/%Y %H:%M:%S')}"
            )
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": settings.TELEGRAM_CHAT_ID,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                )
            return resp.status_code == 200
        except Exception as exc:
            logger.error(f"Error enviando alerta Telegram: {exc}")
            return False