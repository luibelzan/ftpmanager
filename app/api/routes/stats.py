"""
Router de estadísticas de procesamiento — app/api/routes/stats.py

Cada distribuidora tiene su propia base de datos en el mismo PostgreSQL,
con schema 'core'. Las conexiones se crean dinámicamente y se cachean.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import asyncpg
import asyncio
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["Estadísticas"])

# Cache de pools por distribuidora
_pools: dict[str, asyncpg.Pool] = {}
_pools_lock = asyncio.Lock()


def _build_dsn(distribuidora: str) -> str:
    """Construye el DSN para una BD de distribuidora a partir del DATABASE_URL."""
    # DATABASE_URL: postgresql+asyncpg://user:pass@host:port/ftpmanager
    base = settings.DATABASE_URL.replace("postgresql+asyncpg://", "")
    credentials, _ = base.rsplit("/", 1)
    return f"postgresql://{credentials}/{distribuidora}"


async def get_pool(distribuidora: str) -> asyncpg.Pool:
    async with _pools_lock:
        if distribuidora not in _pools:
            dsn = _build_dsn(distribuidora)
            try:
                pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3, command_timeout=30)
                _pools[distribuidora] = pool
                logger.info(f"Pool creado para: {distribuidora}")
            except Exception as e:
                raise HTTPException(503, detail=f"No se pudo conectar a {distribuidora}: {e}")
        return _pools[distribuidora]


async def close_all_pools():
    for name, pool in _pools.items():
        try:
            await pool.close()
        except Exception:
            pass
    _pools.clear()


# ─── GET /stats/ — lista de distribuidoras ────────────────────────────────────

@router.get("/")
async def list_distribuidoras():
    """Lista las BDs de distribuidoras disponibles en PostgreSQL."""
    try:
        conn = await asyncpg.connect(_build_dsn("postgres"))
        rows = await conn.fetch(
            """
            SELECT datname FROM pg_database
            WHERE datistemplate = false
            AND datname NOT IN ('postgres', 'ftpmanager', 'template0', 'template1')
            ORDER BY datname
            """
        )
        await conn.close()
        return {"distribuidoras": [row["datname"] for row in rows]}
    except Exception as e:
        logger.error(f"Error listando distribuidoras: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── GET /stats/{distribuidora}/resumen ───────────────────────────────────────

@router.get("/{distribuidora}/resumen")
async def get_resumen(
    distribuidora: str,
    horas: int = Query(24, ge=1, le=720),
):
    pool = await get_pool(distribuidora)

    resumen = {
        "distribuidora": distribuidora,
        "horas": horas,
        "total": 0,
        "procesados": 0,
        "vacios": 0,
        "errores": 0,
        "desconocidos": 0,
    }

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT resultado, COUNT(*)::int AS n
                FROM core.t_procesamiento_log
                WHERE fecha_procesado > now() - ($1 || ' hours')::interval
                GROUP BY resultado
                """,
                str(horas),
            )
            for row in rows:
                resumen["total"] += row["n"]
                r = row["resultado"]
                if r == "PROCESADO":     resumen["procesados"]    = row["n"]
                elif r == "VACIO":       resumen["vacios"]        = row["n"]
                elif r == "ERROR":       resumen["errores"]       = row["n"]
                elif r == "DESCONOCIDO": resumen["desconocidos"]  = row["n"]
    except asyncpg.exceptions.UndefinedTableError:
        pass
    except Exception as e:
        logger.warning(f"[{distribuidora}] Error resumen: {e}")

    return resumen


@router.get("/resumen-global")
async def get_resumen_global():
    from app.db.database import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE resultado = 'PROCESADO')   AS procesados,
                COUNT(*) FILTER (WHERE resultado = 'VACIO')       AS vacios,
                COUNT(*) FILTER (WHERE resultado = 'ERROR')       AS errores,
                COUNT(*) FILTER (WHERE resultado = 'DESCONOCIDO') AS desconocidos,
                COUNT(*)                                          AS total
            FROM stats_resumen_cache
            WHERE fecha_procesado > now() - (24 || ' hours')::interval
        """))

        row = result.fetchone()

    return {
        "total":         row[4],
        "procesados":    row[0],
        "vacios":        row[1],
        "errores":       row[2],
        "desconocidos":  row[3],
    }


# ─── GET /stats/{distribuidora}/tipos ─────────────────────────────────────────

@router.get("/{distribuidora}/tipos")
async def get_stats_por_tipo(distribuidora: str):
    pool = await get_pool(distribuidora)
    resultados = []

    try:
        async with pool.acquire() as conn:
            tipos = await conn.fetch(
                "SELECT DISTINCT tipo FROM core.t_procesamiento_log ORDER BY tipo"
            )
            for row in tipos:
                tipo = row["tipo"]
                tabla = f"t_{tipo.lower()}"
                tabla_error = f"{tabla}_error"
                procesados = 0
                errores = 0

                try:
                    procesados = await conn.fetchval(
                        f"SELECT COUNT(DISTINCT nombre_fichero)::int FROM core.{tabla}"
                    ) or 0
                except Exception:
                    continue

                try:
                    errores = await conn.fetchval(
                        f"SELECT COUNT(DISTINCT nombre_fichero)::int FROM core.{tabla_error}"
                    ) or 0
                except Exception:
                    errores = 0

                resultados.append({"tipo": tipo, "procesados": procesados, "errores": errores})

    except asyncpg.exceptions.UndefinedTableError:
        pass
    except Exception as e:
        logger.warning(f"[{distribuidora}] Error tipos: {e}")

    return {"distribuidora": distribuidora, "porTipo": resultados}


# ─── GET /stats/{distribuidora}/historico ─────────────────────────────────────

@router.get("/{distribuidora}/historico")
async def get_historico(
    distribuidora: str,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    tipo: Optional[str] = None,
    resultado: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    pool = await get_pool(distribuidora)

    where_clauses = []
    params: list = []

    if desde:
        params.append(desde)
        where_clauses.append(f"fecha_procesado >= ${len(params)}")
    if hasta:
        params.append(hasta)
        where_clauses.append(f"fecha_procesado <= ${len(params)}")
    if tipo:
        params.append(tipo.upper())
        where_clauses.append(f"tipo = ${len(params)}")
    if resultado:
        params.append(resultado.upper())
        where_clauses.append(f"resultado = ${len(params)}")

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    try:
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                f"SELECT COUNT(*)::int FROM core.t_procesamiento_log {where_sql}",
                *params,
            ) or 0

            data_params = params + [limit, offset]
            rows = await conn.fetch(
                f"""
                SELECT nombre_fichero, tipo, resultado,
                       filas_principales, filas_error, mensaje, fecha_procesado
                FROM core.t_procesamiento_log
                {where_sql}
                ORDER BY fecha_procesado DESC
                LIMIT ${len(data_params) - 1} OFFSET ${len(data_params)}
                """,
                *data_params,
            )

            filas = [
                {
                    "nombreFichero":    row["nombre_fichero"],
                    "tipo":             row["tipo"],
                    "resultado":        row["resultado"],
                    "filasPrincipales": row["filas_principales"],
                    "filasError":       row["filas_error"],
                    "mensaje":          row["mensaje"],
                    "fechaProcesado":   row["fecha_procesado"].isoformat()
                                        if row["fecha_procesado"] else None,
                }
                for row in rows
            ]

            return {"distribuidora": distribuidora, "total": total, "filas": filas}

    except asyncpg.exceptions.UndefinedTableError:
        return {"distribuidora": distribuidora, "total": 0, "filas": []}
    except Exception as e:
        logger.error(f"[{distribuidora}] Error histórico: {e}")
        raise HTTPException(status_code=500, detail=str(e))