from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.schemas import (
    ClientCreate, ClientUpdate, ClientOut, ClientSummary,
    DownloadRuleCreate, DownloadRuleOut,
    FtpTestRequest, FtpTestResult,
)
from app.services.client_service import ClientService
from app.services.ftp_engine import FtpEngine
from app.services.scheduler_service import SchedulerService
from app.services.job_runner import JobRunner

router = APIRouter(prefix="/clients", tags=["Clientes"])

# ─── Test de conexión FTP ─────────────────────────────────────────────────────

@router.post("/test-connection", response_model=FtpTestResult)
async def test_ftp_connection(data: FtpTestRequest):
    result = FtpEngine.test_connection(
        host=data.ftp_host, port=data.ftp_port, protocol=data.ftp_protocol,
        user=data.ftp_user, password=data.ftp_password,
        timeout=data.ftp_timeout, passive=data.ftp_passive,
    )
    return result


@router.get("/", response_model=list[ClientSummary])
async def list_clients(active_only: bool = False, db: AsyncSession = Depends(get_db)):
    return await ClientService.get_all(db, active_only=active_only)


@router.post("/", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
async def create_client(data: ClientCreate, db: AsyncSession = Depends(get_db)):
    existing = await ClientService.get_by_code(db, data.code)
    if existing:
        raise HTTPException(status_code=409, detail=f"Ya existe un cliente con código {data.code}")
    client = await ClientService.create(db, data)
    if client.schedule_cron and client.schedule_active:
        SchedulerService.add_or_update(client)
    return client


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(client_id: str, db: AsyncSession = Depends(get_db)):
    client = await ClientService.get_by_id(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return client


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(client_id: str, data: ClientUpdate, db: AsyncSession = Depends(get_db)):
    client = await ClientService.update(db, client_id, data)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    SchedulerService.add_or_update(client)
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(client_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await ClientService.delete(db, client_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    SchedulerService.remove(client_id)


@router.post("/{client_id}/toggle", response_model=ClientOut)
async def toggle_client(client_id: str, db: AsyncSession = Depends(get_db)):
    client = await ClientService.toggle_active(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if client.active:
        SchedulerService.add_or_update(client)
    else:
        SchedulerService.remove(client_id)
    return client


# ─── Ejecución manual ─────────────────────────────────────────────────────────

@router.post("/{client_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_now(client_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    client = await ClientService.get_by_id(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    background_tasks.add_task(JobRunner.run_by_id, client_id, "manual")
    return {"message": f"Ejecución manual iniciada para {client.name}", "client_id": client_id}


# ─── Reglas de descarga ───────────────────────────────────────────────────────

@router.post("/{client_id}/rules", response_model=DownloadRuleOut, status_code=status.HTTP_201_CREATED)
async def add_rule(client_id: str, data: DownloadRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = await ClientService.add_rule(db, client_id, data.model_dump())
    if not rule:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await ClientService.delete_rule(db, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Regla no encontrada")


