import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import engine, Base
from app.api.routes.clients import router as clients_router
from app.api.routes.dashboard import dashboard_router, alerts_router, jobs_router
from app.services.scheduler_service import scheduler, SchedulerService
from app.api.routes.stats import router as stats_router, close_all_pools


# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando FTP Manager...")

    # Crear tablas si no existen (en producción usar Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Arrancar scheduler y cargar clientes
    scheduler.start()
    await SchedulerService.load_all_clients()
    logger.info("Scheduler iniciado")

    yield

    await close_all_pools()
    logger.info("Apagando FTP Manager...")
    scheduler.shutdown(wait=False)


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FTP Manager API",
    description="Gestor de descargas FTP/SFTP multicliente con scheduler y alertas",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(clients_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(stats_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
