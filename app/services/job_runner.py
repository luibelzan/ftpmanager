import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Client, JobExecution, JobStatus, AlertType, AlertLevel
from app.services.ftp_engine import FtpEngine
from app.services.vpn_service import VpnService
from app.services.alert_service import AlertService
from app.db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class JobRunner:

    @staticmethod
    async def run(client: Client, triggered_by: str = "scheduler") -> JobExecution:
        async with AsyncSessionLocal() as db:
            execution = JobExecution(
                client_id=client.id,
                status=JobStatus.RUNNING,
                triggered_by=triggered_by,
                vpn_used=client.vpn_required,
            )
            db.add(execution)
            await db.flush()
            exec_id = execution.id

            vpn_ok = True
            vpn_error = None

            # ── 1. VPN ────────────────────────────────────────────────────────
            if client.vpn_required:
                try:
                    await VpnService.connect(client)
                    logger.info(f"[{client.code}] VPN activa")
                except Exception as exc:
                    vpn_ok = False
                    vpn_error = str(exc)
                    logger.error(f"[{client.code}] VPN fallida: {exc}")
                    await AlertService.create(
                        db,
                        alert_type=AlertType.VPN_DOWN,
                        level=AlertLevel.CRITICAL,
                        message=f"No se pudo levantar el túnel VPN para {client.name}: {exc}",
                        client=client,
                        job_execution_id=exec_id,
                    )

            if not vpn_ok:
                execution.status = JobStatus.FAILED
                execution.finished_at = datetime.utcnow()
                execution.error_message = f"VPN no disponible: {vpn_error}"
                execution.duration_seconds = 0.0
                await db.commit()
                return execution

            # ── 2. FTP ────────────────────────────────────────────────────────
            engine = FtpEngine(client)
            try:
                result = engine.execute_rules()
            except Exception as exc:
                result_error = str(exc)
                execution.status = JobStatus.FAILED
                execution.finished_at = datetime.utcnow()
                execution.error_message = result_error
                await AlertService.create(
                    db,
                    alert_type=AlertType.FTP_CONNECTION_ERROR,
                    level=AlertLevel.CRITICAL,
                    message=f"Error de conexión FTP para {client.name}: {result_error}",
                    client=client,
                    job_execution_id=exec_id,
                )
                await db.commit()
                return execution
            finally:
                if client.vpn_required:
                    VpnService.disconnect(client.code)

            # ── 3. Registrar resultado ────────────────────────────────────────
            execution.finished_at = datetime.utcnow()
            execution.files_downloaded = result.files_downloaded
            execution.files_by_type = result.files_by_type
            execution.duration_seconds = result.duration_seconds

            if not result.success:
                execution.status = JobStatus.FAILED
                execution.error_message = result.error_message
                await AlertService.create(
                    db,
                    alert_type=AlertType.FTP_CONNECTION_ERROR,
                    level=AlertLevel.CRITICAL,
                    message=f"Error FTP para {client.name}: {result.error_message}",
                    client=client,
                    job_execution_id=exec_id,
                )
            elif result.files_downloaded == 0:
                execution.status = JobStatus.SUCCESS
                await AlertService.create(
                    db,
                    alert_type=AlertType.FTP_NO_FILES,
                    level=AlertLevel.WARNING,
                    message=f"Conexión OK pero sin ficheros descargados para {client.name}",
                    client=client,
                    job_execution_id=exec_id,
                )
            else:
                execution.status = JobStatus.SUCCESS

            await db.commit()
            logger.info(
                f"[{client.code}] Ejecución finalizada: "
                f"{execution.status} · {result.files_downloaded} ficheros"
            )
            return execution

    @staticmethod
    async def run_by_id(client_id: str, triggered_by: str = "manual") -> JobExecution:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.models import DownloadRule

        async with AsyncSessionLocal() as db:
            q = (
                select(Client)
                .options(selectinload(Client.download_rules).selectinload(DownloadRule.file_patterns))
                .where(Client.id == client_id)
            )
            result = await db.execute(q)
            client = result.scalar_one_or_none()

        if not client:
            raise ValueError(f"Cliente {client_id} no encontrado")

        return await JobRunner.run(client, triggered_by=triggered_by)