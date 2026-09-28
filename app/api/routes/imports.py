"""
app/api/routes/imports.py

Endpoint para importar ficheros PIC (Excel) a la tabla core.t_cups
de la BD de una distribuidora.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import io
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/imports", tags=["Importaciones"])


# ─── Mapeo columnas Excel → columnas t_cups ───────────────────────────────────

COL_MAP = {
    "CUPS":                          "id_cups",
    "CLIENTE":                       "nom_cups",
    "NIF_RESPONSABLE":               "cif_cups",
    "DIRECCIONSUMINISTRO":           "dir_cups",
    "TARIFA":                        "tip_tarifa",
    "POLIZA":                        "cod_poliza",
    "NUMEROSERIE":                   "id_cnt",
    "MARCA":                         "des_fabricante",
    "TIPOEQUIPO":                    "tip_equipo",
    "TIPO PUNTO MEDIDA":             "tip_punto_medida",
    "TIPO INSTALACION":              "tip_tipo_frontera",
    "MEDIO LECTURA":                 "tip_lectura",
    "FASE":                          "cod_fase",
    "LINEA":                         "id_linea",
    "CODTRAFO":                      "id_trafo",
    "CODCT":                         "id_ct",
    "NIVELTENSIONSUMINISTRO":        "des_nivel_tension",
    "POTENCIARECONOCIDA":            "val_potencia_adscrita",
    "REF. CATASTRAL":                "cod_catastro",
    "FECHAALTA":                     "fec_fecha_alta",
    "FECHAFIN":                      "fec_fecha_baja",
    "TIENEMAXIMETRO":                "ind_maximetro",
    "BONO SOCIAL":                   "ind_habitual",
    "SITUACIÓN":                     "cups_estado",
    "SITUACION":                     "cups_estado",
    "TIPOPUNTO":                     "tip_punto_medida",
    "NOMBRE DESCRIPTIVO DEL PUNTO":  "nom_calle",
    "TIENETELEMETRIA":               "tip_lectura",
    "PROPIEDADEQUIPO":               "des_propiedad",
    "CODIGOAUTONOMICO":              "cod_clave_autonomica",
    "TIPOTELGESTION":                "tip_lectura",
}

# ─── Longitudes máximas por columna ───────────────────────────────────────────

COL_MAX_LEN = {
    "id_cups":              30,
    "nom_cups":             50,
    "cif_cups":             12,
    "dir_cups":             80,
    "cp_cups":               6,
    "cod_catastro":         20,
    "cod_acometida":        30,
    "cod_nodo":             15,
    "cod_zona":             30,
    "cod_sector":           30,
    "cod_subsector":        30,
    "lat_cups":             20,
    "lon_cups":             20,
    "des_utmx":             20,
    "des_utmy":             20,
    "cups_estado":           1,
    "tip_cups":              2,
    "id_ct":                15,
    "tip_tarifa":           10,
    "tip_tipo_frontera":     3,
    "cod_codigo_mytc":      15,
    "id_distribuidora":      3,
    "des_nivel_tension":    10,
    "cod_poliza":           30,
    "id_cnt":               15,
    "des_propiedad":         1,
    "des_fabricante":       15,
    "tip_equipo":            3,
    "cod_fase":              1,
    "id_linea":             15,
    "id_trafo":             15,
    "nom_calle":            50,
    "cod_portal":           12,
    "nom_comercializadora": 80,
    "tip_lectura":          10,
    "ind_habitual":          1,
    "ind_maximetro":         1,
    "ind_reactiva":          1,
    "ind_repetidor":         1,
    "ind_autoconsumo":       1,
}

# Columnas numéricas
NUMERIC_COLS = {"val_potencia_adscrita", "val_potencia_contratada", "tip_punto_medida", "cod_clave_autonomica"}

# Columnas que deben normalizarse a S/N
SI_NO_COLS = {"ind_habitual", "ind_maximetro", "ind_reactiva", "ind_repetidor", "ind_autoconsumo"}

# Columnas de fecha
DATE_COLS = {"fec_fecha_alta", "fec_fecha_baja", "fec_registro"}

# Mapeo prefijo CUPS → dso_type
PREFIJO_DSO_TYPE = {
    'ES0412': 1,  # CIDE
    'ES0130': 2,  # INFEDER
    'ES0031': 3,  # LUXIDA
    'ES0534': 4,  # ACSI
}

DSO_TYPE_NOMBRE = {1: 'CIDE', 2: 'INFEDER', 3: 'LUXIDA', 4: 'ACSI', 5: 'OTROS'}

# Normalización cups_estado
ESTADO_MAP = {
    "ACTIVO": "A", "ACTIVA": "A", "A": "A", "ALTA": "A",
    "BAJA":   "B", "B": "B",
    "SUSPENDIDO": "S", "SUSPENDIDA": "S", "S": "S",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def normalizar_sino(val: str) -> str:
    v = (val or "").strip().upper()
    if v in ("S", "SI", "SÍ", "1", "TRUE", "YES", "Y", "VERDADERO"): return "S"
    return "N"


def normalizar_valor(db_col: str, val: str):
    """Normaliza y trunca un valor según el tipo de columna."""
    if not val or val.lower() in ("nan", "none", "nat", ""):
        return None

    if db_col in NUMERIC_COLS:
        try:
            return float(val.replace(",", "."))
        except Exception:
            return None

    if db_col in DATE_COLS:
        import pandas as pd
        try:
            ts = pd.to_datetime(val, dayfirst=True, errors="coerce")
            return None if pd.isna(ts) else ts.date()
        except Exception:
            return None

    if db_col in SI_NO_COLS:
        return normalizar_sino(val)

    if db_col == "cups_estado":
        return ESTADO_MAP.get(val.strip().upper(), val.strip()[:1]) or None

    max_len = COL_MAX_LEN.get(db_col, 200)
    return val[:max_len] if val else None


def is_baja(fila: dict) -> bool:
    estado = (fila.get("cups_estado") or "").strip().upper()
    fec_baja = fila.get("fec_fecha_baja")
    return estado not in ("", "A") or fec_baja is not None


# ─── Validación distribuidora ─────────────────────────────────────────────────

async def validar_distribuidora(pool, cups_prefijo: str) -> dict:
    dso_type_fichero = PREFIJO_DSO_TYPE.get(cups_prefijo)
    if not dso_type_fichero:
        return {"valido": False, "mensaje": f"Prefijo CUPS '{cups_prefijo}' no reconocido"}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT dso_id, dso_name, dso_type FROM core.t_distribuidora"
            )
            if not rows:
                return {"valido": False, "mensaje": "t_distribuidora está vacía en esta BD"}

            tipos_bd = [int(row["dso_type"]) for row in rows if row["dso_type"] is not None]
            nombres_bd = [row["dso_name"] for row in rows if row["dso_name"]]

            if dso_type_fichero in tipos_bd:
                return {"valido": True, "mensaje": None}

            nombre_fichero = DSO_TYPE_NOMBRE.get(dso_type_fichero, cups_prefijo)
            return {
                "valido": False,
                "mensaje": (
                    f"El fichero es de tipo '{nombre_fichero}' ({cups_prefijo}) "
                    f"pero la BD destino contiene: {', '.join(filter(None, nombres_bd))}"
                )
            }
    except Exception as e:
        return {"valido": False, "mensaje": f"Error consultando t_distribuidora: {e}"}


# ─── Endpoint principal ───────────────────────────────────────────────────────

@router.post("/pic")
async def import_pic(
    distribuidora_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Importa un fichero PIC (Excel .xlsx) a core.t_cups de la BD indicada.
    Devuelve: total CUPS en fichero, nuevos, actualizados, dados de baja, errores.
    """
    import pandas as pd
    from app.api.routes.stats import get_pool

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "El fichero debe ser .xlsx o .xls")

    # ── Leer Excel ────────────────────────────────────────────────────────────
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents), dtype=str, na_filter=False)
    except Exception as e:
        raise HTTPException(400, f"Error leyendo el Excel: {e}")

    df.columns = [c.strip() for c in df.columns]

    if "CUPS" not in df.columns:
        raise HTTPException(400, "El fichero no tiene columna CUPS")

    # ── Detectar prefijo y validar distribuidora ──────────────────────────────
    primer_cups = df["CUPS"].replace("", None).dropna().iloc[0].strip() if not df["CUPS"].replace("", None).dropna().empty else ""
    cups_prefijo = primer_cups[:6]

    pool = await get_pool(distribuidora_id)
    validacion = await validar_distribuidora(pool, cups_prefijo)
    if not validacion["valido"]:
        raise HTTPException(400, detail=validacion["mensaje"])

    # ── Construir filas ───────────────────────────────────────────────────────
    filas = []
    for _, row in df.iterrows():
        cups = str(row.get("CUPS", "")).strip()
        if not cups or cups.lower() in ("nan", "none", ""):
            continue

        fila: dict = {"id_cups": cups[:30]}

        for excel_col, db_col in COL_MAP.items():
            if excel_col == "CUPS" or excel_col not in df.columns:
                continue
            raw = str(row.get(excel_col, "")).strip()
            fila[db_col] = normalizar_valor(db_col, raw)

        fila["_baja"] = is_baja(fila)
        filas.append(fila)

    total = len(filas)
    if total == 0:
        return {"total": 0, "nuevos": 0, "actualizados": 0, "bajas": 0, "errores": 0}

    # ── Insertar / actualizar en BD ───────────────────────────────────────────
    nuevos = actualizados = bajas = errores = 0

    async with pool.acquire() as conn:
        existing_set = {
            r["id_cups"]
            for r in await conn.fetch("SELECT id_cups FROM core.t_cups")
        }

        for fila in filas:
            cups = fila["id_cups"]
            es_baja = fila.pop("_baja", False)
            if es_baja:
                bajas += 1

            # Solo columnas con valor no nulo
            cols = [k for k, v in fila.items() if v is not None]
            vals = [fila[k] for k in cols]

            try:
                if cups not in existing_set:
                    placeholders = ", ".join(f"${i+1}" for i in range(len(cols)))
                    cols_sql = ", ".join(f'"{c}"' for c in cols)
                    await conn.execute(
                        f"INSERT INTO core.t_cups ({cols_sql}) VALUES ({placeholders})",
                        *vals
                    )
                    nuevos += 1
                else:
                    update_cols = [c for c in cols if c != "id_cups"]
                    update_vals = [fila[c] for c in update_cols]
                    if update_cols:
                        n = len(update_cols)
                        set_sql = ", ".join(f'"{c}" = ${i+1}' for i, c in enumerate(update_cols))
                        check_sql = " OR ".join(
                            f'"{c}" IS DISTINCT FROM ${i+1}'
                            for i, c in enumerate(update_cols)
                        )
                        hay_cambios = await conn.fetchval(
                            f'SELECT EXISTS(SELECT 1 FROM core.t_cups WHERE id_cups = ${n+1} AND ({check_sql}))',
                            *update_vals, cups
                        )
                        if hay_cambios:
                            await conn.execute(
                                f'UPDATE core.t_cups SET {set_sql} WHERE id_cups = ${n+1}',
                                *update_vals, cups
                            )
                            actualizados += 1

            except Exception as e:
                logger.warning(f"Error procesando CUPS {cups}: {e}")
                errores += 1

    return {
        "total":        total,
        "nuevos":       nuevos,
        "actualizados": actualizados,
        "bajas":        bajas,
        "errores":      errores,
        "distribuidora": distribuidora_id,
        "fichero":      file.filename,
    }