"""
app/api/routes/imports.py  — v5

Importación de ficheros PIC/Contratos a core.t_cups2.
Soporta 4 formatos: CIDE, LUXIDA, INFEDER, ACSI.
ACSI: fichero multi-hoja, una hoja por distribuidora.
Incluye detalle de cambios por CUPS.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import io
import re
import logging
from datetime import date

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/imports", tags=["Importaciones"])


# ─── Identificación de distribuidoras ────────────────────────────────────────

CUPS_DSO_ID = {
    '0412': 'CIDE',
    '0031': 'LUXIDA',
    '0130': 'INFEDER',
    '0534': 'ACSI',
}

DSO_TYPE = {'CIDE': 1, 'INFEDER': 2, 'LUXIDA': 3, 'ACSI': 4, 'OTROS': 5}


# ─── Detección de formato ─────────────────────────────────────────────────────

def detectar_formato(columnas: list[str]) -> str:
    cols = set(columnas)
    # ACSI: cabeceras en minúsculas con 'cups', 'n_serie', 'tarofi'
    if 'cups' in cols and 'n_serie' in cols and 'tarofi' in cols:
        return 'ACSI'
    if 'Contador' in cols and 'Estado' in cols and 'Distribuidora' in cols:
        return 'CIDE'
    if 'CUPS' in cols and 'NUMEROSERIE' in cols and 'TARIFA' in cols:
        return 'CIDE_OLD'
    if 'CUPS' in cols and 'CONTRATO' in cols:
        return 'LUXIDA'
    if 'IDENTIFICADOR' in cols or 'CIF' in cols:
        return 'INFEDER'
    return 'DESCONOCIDO'


# ─── Mapeos Excel → t_cups2 ───────────────────────────────────────────────────

COL_MAP_CIDE = {
    'CUPS':                                  'id_cups',
    'Contador':                              'id_cnt',
    'Poliza':                                'id_poliza',
    'Cliente':                               'nom_cups',
    'Cliente Id. Fiscal':                    'cif_cups',
    'Dir Suministro: Cod. Postal':           'cp_cups',
    'Estado':                                'estado_cups',
    'Nivel tensión punto de medida':         'tip_cups',
    'Comercializadora':                      'nom_comercializadora',
    'Tarifa':                                'tip_tarifa',
    'Potencia contratada P1':                'pot_p1',
    'Potencia contratada P2':                'pot_p2',
    'Potencia contratada P3':                'pot_p3',
    'Potencia contratada P4':                'pot_p4',
    'Potencia contratada P5':                'pot_p5',
    'Potencia contratada P6':                'pot_p6',
    'Contador: Tipo':                        'tip_cnt',
    'Modo de control de potencia':           'ind_maximetro',
    'Autoconsumo':                           'ind_autoconsumo',
    'Casa cerrada':                          'ind_casacerrada',
    'Bono Social':                           'ind_bonosocial',
    'Vehículo Eléctrico':                    'ind_cargador',
    'Fecha inicio':                          'fec_alta_cups',
    'Fecha fin':                             'fec_baja_cups',
    'Fecha de primera Instalación Contador': 'fec_instalacion_cnt',
    'Contador: Inaccesible':                 'ind_inaccesible',
    'Tipo de punto':                         'tip_pm',
    'Línea Código':                          'id_linea',
    'CT Código':                             'id_ct',
    'Trafo Código':                          'id_trafo',
    'Tipo de fase':                          'id_fase',
}

COL_MAP_CIDE_OLD = {
    'CUPS':               'id_cups',
    'NUMEROSERIE':        'id_cnt',
    'POLIZA':             'id_poliza',
    'CLIENTE':            'nom_cups',
    'NIF_RESPONSABLE':    'cif_cups',
    'TARIFA':             'tip_tarifa',
    'SITUACIÓN':          'estado_cups',
    'SITUACION':          'estado_cups',
    'FECHAALTA':          'fec_alta_cups',
    'FECHAFIN':           'fec_baja_cups',
    'TIENEMAXIMETRO':     'ind_maximetro',
    'BONO SOCIAL':        'ind_bonosocial',
    'POTENCIARECONOCIDA': 'pot_p1',
    'NIVELTENSIONSUMINISTRO': 'tip_cups',
    'CODCT':              'id_ct',
    'CODTRAFO':           'id_trafo',
    'LINEA':              'id_linea',
    'FASE':               'id_fase',
    'TIPOEQUIPO':         'tip_cnt',
    'TIPO PUNTO MEDIDA':  'tip_pm',
}

COL_MAP_ACSI = {
    'cups':        'id_cups',
    'poliza':      'id_poliza',
    'n_serie':     'id_cnt',
    'direccion':   'dir_cups',
    'cod_postal':  'cp_cups',
    'tarofi':      'tip_tarifa',
    'pot_p1':      'pot_p1',
    'pot_p2':      'pot_p2',
    'pot_p3':      'pot_p3',
    'pot_p4':      'pot_p4',
    'pot_p5':      'pot_p5',
    'pot_p6':      'pot_p6',
    'maximetro':   'ind_maximetro',
    'autoconsumo': 'ind_autoconsumo',
}

COL_MAP_LUXIDA  = {}
COL_MAP_INFEDER = {}

FORMATO_MAP = {
    'CIDE':     COL_MAP_CIDE,
    'CIDE_OLD': COL_MAP_CIDE_OLD,
    'ACSI':     COL_MAP_ACSI,
    'LUXIDA':   COL_MAP_LUXIDA,
    'INFEDER':  COL_MAP_INFEDER,
}

# Columna CUPS según formato
CUPS_COL = {
    'CIDE':     'CUPS',
    'CIDE_OLD': 'CUPS',
    'ACSI':     'cups',
    'LUXIDA':   'CUPS',
    'INFEDER':  'CUPS',
}


# ─── Longitudes máximas t_cups2 ───────────────────────────────────────────────

COL_MAX_LEN = {
    'id_cups':             30, 'id_cnt':              15, 'id_poliza':          30,
    'nom_cups':            50, 'cif_cups':            12, 'dir_cups':           80,
    'cp_cups':              6, 'lat_cups':            20, 'lon_cups':           20,
    'estado_cups':          1, 'tip_cups':             2, 'nom_comercializadora': 80,
    'cod_acometida':       30, 'cod_nodo':            15, 'cod_zona':           30,
    'cod_sector':          30, 'cod_subsector':       30, 'tip_tarifa':         10,
    'tip_cnt':              3, 'id_ct':               15, 'id_trafo':           15,
    'id_linea':            15, 'id_fase':              1, 'ind_maximetro':       1,
    'ind_inaccesible':      1, 'ind_casacerrada':      1, 'ind_repetidor':       1,
    'ind_autoconsumo':      1, 'ind_cargador':         1, 'ind_bonosocial':      1,
}

IND_COLS     = {'ind_maximetro','ind_inaccesible','ind_casacerrada','ind_repetidor',
                'ind_autoconsumo','ind_cargador','ind_bonosocial'}
NUMERIC_COLS = {'pot_p1','pot_p2','pot_p3','pot_p4','pot_p5','pot_p6'}
DATE_COLS    = {'fec_alta_cups','fec_baja_cups','fec_instalacion_cnt','fec_registro'}

ESTADO_MAP = {
    'ALTA':'A', 'A':'A',
    'BAJA':'B', 'B':'B',
    'TEMPORAL':'T', 'T':'T',
    'SUSPENDIDO':'S', 'SUSPENDIDA':'S', 'S':'S',
}

TIP_CNT_MAP = {
    'TELEGESTIÓN':'TG', 'TELEGESTION':'TG', 'TG':'TG',
    'TELEMEDIDA':'TM', 'TM':'TM',
}

TENSION_MAP = {'BT':'BT','MT':'MT','AT':'AT','B':'BT','M':'MT'}

RE_CNT_TELGE = re.compile(r'^[A-Z]{2,4}\d{8,12}$', re.IGNORECASE)

FECHA_DEFAULT = date(2020, 1, 1)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def limpiar_para_pg(val):
    if isinstance(val, bytes):
        return val.decode('utf-8', errors='ignore')
    if isinstance(val, bool):
        return 'S' if val else 'N'
    return val


def normalizar_sino(val: str) -> str:
    v = (val or '').strip().upper()
    return 'S' if v in ('S','SI','SÍ','1','TRUE','YES','Y','VERDADERO') else 'N'


def normalizar_fecha(val: str):
    import pandas as pd
    if not val or str(val).lower() in ('nan','none','nat',''):
        return None
    try:
        ts = pd.to_datetime(val, dayfirst=True, errors='coerce')
        return None if pd.isna(ts) else ts.date()
    except Exception:
        return None


def normalizar_potencia_w(val: str) -> float | None:
    if not val or str(val).lower() in ('nan','none',''):
        return None
    try:
        v = float(str(val).replace(',','.'))
        return round(v * 1000, 2) if v <= 1000 else v
    except Exception:
        return None


def tip_pm_por_potencia(pot_p1_w: float | None) -> int | None:
    if pot_p1_w is None:
        return None
    if pot_p1_w <= 15000:   return 5
    if pot_p1_w <= 50000:   return 4
    if pot_p1_w <= 450000:  return 3
    if pot_p1_w <= 1000000: return 2
    return 1


def normalizar_cups(cups_raw: str) -> str:
    return (cups_raw or '').strip()[:20]


def normalizar_valor(db_col: str, val: str):
    if not val or str(val).lower() in ('nan','none','nat',''):
        return None

    if db_col in DATE_COLS:
        return normalizar_fecha(val)

    if db_col in NUMERIC_COLS:
        return normalizar_potencia_w(val)

    if db_col in IND_COLS:
        return normalizar_sino(val)

    if db_col == 'estado_cups':
        return ESTADO_MAP.get(val.strip().upper(), val.strip()[:1]) or None

    if db_col == 'tip_cnt':
        return TIP_CNT_MAP.get(val.strip().upper(), 'ND')

    if db_col == 'tip_cups':
        return TENSION_MAP.get(val.strip().upper(), val.strip()[:2]) or None

    if db_col == 'ind_maximetro':
        v = val.strip().upper()
        return 'S' if 'MAXI' in v or v == 'S' else 'N'

    if db_col == 'ind_autoconsumo':
        return 'S' if val.strip().upper() not in ('NO','N','0','') else 'N'

    if db_col == 'tip_pm':
        try:
            return int(float(val.replace(',','.')))
        except Exception:
            return None

    max_len = COL_MAX_LEN.get(db_col, 200)
    return str(val)[:max_len] if val else None


def normalizar_cmp(v):
    """Normaliza un valor para comparación evitando falsos positivos."""
    if v is None:
        return None
    try:
        from decimal import Decimal
        if isinstance(v, (int, float, Decimal)):
            return round(float(v), 2)
        f = float(str(v).replace(',', '.'))
        return round(f, 2)
    except (ValueError, TypeError):
        pass
    if isinstance(v, str):
        return v.strip()
    return v


# ─── Validaciones ─────────────────────────────────────────────────────────────

def validar_registro(fila: dict, cups_raw: str, vistos: set) -> list[str]:
    avisos = []
    cups = fila.get('id_cups', '')

    if len(cups) < 20:
        avisos.append(f'CUPS corto ({len(cups)} chars)')

    cnt = (fila.get('id_cnt') or '').strip()
    if not cnt:
        avisos.append('Sin número de serie del contador')
    elif not RE_CNT_TELGE.match(cnt):
        avisos.append(f'Formato contador no estándar: {cnt}')

    if cups in vistos:
        avisos.append('CUPS duplicado en el fichero')
    else:
        vistos.add(cups)

    tarifa = (fila.get('tip_tarifa') or '').strip()
    pot = fila.get('pot_p1')
    if pot is not None:
        if tarifa.startswith('2.0') and pot > 15000:
            avisos.append(f'Tarifa {tarifa} con potencia {pot}W > 15kW')
        if tarifa.startswith('3.0') and pot <= 15000:
            avisos.append(f'Tarifa {tarifa} con potencia {pot}W <= 15kW')

    return avisos


# ─── Validación distribuidora ─────────────────────────────────────────────────

async def validar_distribuidora(pool, cups_prefijo: str, formato: str = '') -> dict:
    tipo_erp_esperado = DSO_TYPE.get(formato.split('_')[0], 0)  # CIDE_OLD → CIDE → 1

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch('SELECT dso_id, dso_name, dso_type FROM core.t_distribuidora')
            if not rows:
                return {'valido': False, 'mensaje': 't_distribuidora está vacía en esta BD'}

            # Buscar el dso_id que coincide con el prefijo del CUPS
            dso_match = next(
                (r for r in rows if str(r['dso_id']).strip() == cups_prefijo),
                None
            )

            if not dso_match:
                nombres_bd = [r['dso_name'] for r in rows if r['dso_name']]
                return {
                    'valido': False,
                    'mensaje': (
                        f"El prefijo '{cups_prefijo}' no coincide con ninguna distribuidora "
                        f"en esta BD. Distribuidoras registradas: {', '.join(filter(None, nombres_bd))}"
                    )
                }

            # Verificar que el tipo de ERP coincide
            dso_type_bd = int(dso_match['dso_type']) if dso_match['dso_type'] is not None else 0
            if tipo_erp_esperado and dso_type_bd != tipo_erp_esperado:
                tipo_erp_nombre = next(k for k, v in DSO_TYPE.items() if v == dso_type_bd)
                return {
                    'valido': False,
                    'mensaje': (
                        f"El fichero es de tipo '{formato}' pero la distribuidora "
                        f"'{dso_match['dso_name']}' es de tipo ERP '{tipo_erp_nombre}'"
                    )
                }

            return {
                'valido': True,
                'mensaje': None,
                'tipo': next((k for k, v in DSO_TYPE.items() if v == dso_type_bd), 'OTROS')
            }

    except Exception as e:
        return {'valido': False, 'mensaje': f'Error consultando t_distribuidora: {e}'}


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post('/pic')
async def import_pic(
    distribuidora_id: str = Form(...),
    file: UploadFile = File(...),
):
    import pandas as pd
    from app.api.routes.stats import get_pool

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, 'El fichero debe ser .xlsx o .xls')

    contents = await file.read()

    # ── Leer Excel — detectar hoja ────────────────────────────────────────────
    try:
        xl = pd.ExcelFile(io.BytesIO(contents))
        sheet_names = xl.sheet_names

        if 'PUNTOS_ACTIVOS' in sheet_names:
            # CIDE nuevo formato
            sheet = 'PUNTOS_ACTIVOS'
        elif distribuidora_id in sheet_names:
            # ACSI: hoja con el nombre exacto de la distribuidora
            sheet = distribuidora_id
        else:
            # Match case-insensitive
            match = next(
                (s for s in sheet_names if s.lower() == distribuidora_id.lower()),
                None
            )
            if match:
                sheet = match
            elif len(sheet_names) == 1:
                sheet = sheet_names[0]
            else:
                raise HTTPException(
                    400,
                    f"No se encontró la hoja '{distribuidora_id}' en el fichero. "
                    f"Hojas disponibles: {', '.join(sheet_names)}"
                )

        df = pd.read_excel(io.BytesIO(contents), sheet_name=sheet, dtype=str, na_filter=False)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f'Error leyendo el Excel: {e}')

    df.columns = [c.strip() for c in df.columns]

    # ── Detectar formato ──────────────────────────────────────────────────────
    formato = detectar_formato(list(df.columns))
    col_map = FORMATO_MAP.get(formato, {})
    if not col_map:
        raise HTTPException(400, f'Formato no reconocido o no implementado: {formato}')

    # Columna CUPS según formato
    cups_col = CUPS_COL.get(formato, 'CUPS')
    if cups_col not in df.columns:
        raise HTTPException(400, f'El fichero no tiene columna {cups_col}')

    # ── Validar distribuidora ─────────────────────────────────────────────────
    primer_cups = df[cups_col].replace('', None).dropna().iloc[0].strip() \
        if not df[cups_col].replace('', None).dropna().empty else ''
    cups_prefijo = primer_cups[2:6]

    pool = await get_pool(distribuidora_id)
    validacion = await validar_distribuidora(pool, cups_prefijo, formato)
    if not validacion['valido']:
        raise HTTPException(400, detail=validacion['mensaje'])

    tipo_fichero = validacion.get('tipo', 'DESCONOCIDO')

    # ── Construir filas ───────────────────────────────────────────────────────
    filas        = []
    avisos_total = []
    vistos_cups  = set()
    cnt_vistos   = {}

    for _, row in df.iterrows():
        cups_raw = str(row.get(cups_col, '')).strip()
        if not cups_raw or cups_raw.lower() in ('nan', 'none', ''):
            continue

        cups = normalizar_cups(cups_raw)
        fila: dict = {'id_cups': cups}

        # Dirección suministro concatenada (CIDE nuevo)
        if 'Dir Suministro: Tipo de vía' in df.columns:
            partes = [
                str(row.get('Dir Suministro: Tipo de vía', '')).strip(),
                str(row.get('Dir Suministro: Nombre de vía', '')).strip(),
                str(row.get('Dir Suministro: Número', '')).strip(),
            ]
            dir_val = ', '.join(p for p in partes if p and p.lower() not in ('nan','none',''))
            fila['dir_cups'] = dir_val[:80] if dir_val else None

        # Mapear columnas del Excel
        for excel_col, db_col in col_map.items():
            if excel_col == cups_col or excel_col not in df.columns:
                continue
            raw = str(row.get(excel_col, '')).strip()
            fila[db_col] = normalizar_valor(db_col, raw)

        # Potencias: asegurar conversión a W
        for pc in ('pot_p1','pot_p2','pot_p3','pot_p4','pot_p5','pot_p6'):
            if pc in fila and fila[pc] is not None and isinstance(fila[pc], str):
                fila[pc] = normalizar_potencia_w(fila[pc])

        # tip_pm calculado siempre desde pot_p1
        fila['tip_pm'] = tip_pm_por_potencia(fila.get('pot_p1'))

        # Autoconsumo forzado a S cuando venga en el listado (CIDE)
        if 'Autoconsumo' in df.columns:
            v = str(row.get('Autoconsumo', '')).strip().upper()
            fila['ind_autoconsumo'] = 'S' if v not in ('NO','N','0','') else 'N'

        # ind_maximetro: ICP=N, Maxímetro=S (CIDE)
        if 'Modo de control de potencia' in df.columns:
            v = str(row.get('Modo de control de potencia', '')).strip().upper()
            fila['ind_maximetro'] = 'S' if 'MAXI' in v else 'N'

        # Fechas por defecto para ACSI (no vienen en el fichero)
        if formato == 'ACSI':
            if not fila.get('fec_alta_cups'):
                fila['fec_alta_cups'] = FECHA_DEFAULT
            if not fila.get('fec_instalacion_cnt'):
                fila['fec_instalacion_cnt'] = FECHA_DEFAULT
            # Estado por defecto: Alta
            if not fila.get('estado_cups'):
                fila['estado_cups'] = 'A'

        # Detectar contadores duplicados en el fichero
        cnt = (fila.get('id_cnt') or '').strip()
        if cnt:
            if cnt in cnt_vistos:
                avisos_total.append({'cups': cups, 'aviso': f'Mismo contador {cnt} ya visto en {cnt_vistos[cnt]}'})
            else:
                cnt_vistos[cnt] = cups

        for av in validar_registro(fila, cups_raw, vistos_cups):
            avisos_total.append({'cups': cups, 'aviso': av})

        filas.append(fila)

    total = len(filas)
    if total == 0:
        return {'total': 0, 'nuevos': 0, 'actualizados': 0, 'bajas': 0,
                'errores': 0, 'avisos': avisos_total, 'total_avisos': 0,
                'cambios_detalle': [], 'total_cambios_detalle': 0}

    # ── Upsert en t_cups2 ─────────────────────────────────────────────────────
    nuevos = actualizados = bajas = errores = 0
    cambios_detalle = []
    fecha_carga = date.today()

    async with pool.acquire() as conn:
        # Cargar todos los CUPS existentes con todos sus campos de una vez
        update_cols_needed = list(set(
            db_col for db_col in {**COL_MAP_CIDE, **COL_MAP_ACSI}.values()
            if db_col != 'id_cups'
        ) | {'dir_cups'})
        cols_select = ', '.join(f'"{c}"' for c in ['id_cups', 'estado_cups'] + update_cols_needed)
        existing_rows = await conn.fetch(f'SELECT {cols_select} FROM core.t_cups2')
        existing = {r['id_cups']: dict(r) for r in existing_rows}
        cups_en_fichero = {f['id_cups'] for f in filas}

        # Dar de baja CUPS activos que no aparecen en el fichero
        for cups_bd, datos_bd in existing.items():
            estado_bd = datos_bd.get('estado_cups') if isinstance(datos_bd, dict) else datos_bd
            if cups_bd not in cups_en_fichero and (estado_bd or 'A') == 'A':
                try:
                    await conn.execute(
                        "UPDATE core.t_cups2 SET estado_cups = 'B', fec_baja_cups = $1 WHERE id_cups = $2",
                        fecha_carga, cups_bd
                    )
                    bajas += 1
                except Exception as e:
                    logger.warning(f'Error dando de baja {cups_bd}: {e}')

        # Insertar / actualizar
        for fila in filas:
            cups = fila['id_cups']
            cols = [k for k, v in fila.items() if v is not None]
            vals = [limpiar_para_pg(fila[k]) for k in cols]

            try:
                if cups not in existing:
                    placeholders = ', '.join(f'${i+1}' for i in range(len(cols)))
                    cols_sql = ', '.join(f'"{c}"' for c in cols)
                    await conn.execute(
                        f'INSERT INTO core.t_cups2 ({cols_sql}) VALUES ({placeholders})',
                        *vals
                    )
                    nuevos += 1

                else:
                    update_cols = [c for c in cols if c != 'id_cups']
                    update_vals = [limpiar_para_pg(fila[c]) for c in update_cols]
                    if not update_cols:
                        continue

                    n = len(update_cols)
                    fila_actual = existing.get(cups, {})

                    hay_cambio = False
                    cambios_cups = {}
                    for c, val_nuevo in zip(update_cols, update_vals):
                        val_anterior = fila_actual.get(c)
                        ant_cmp = normalizar_cmp(val_anterior)
                        nvo_cmp = normalizar_cmp(val_nuevo)

                        if ant_cmp != nvo_cmp:
                            hay_cambio = True
                            ant_str = str(val_anterior) if val_anterior is not None else None
                            nvo_str = str(val_nuevo)    if val_nuevo    is not None else None
                            cambios_cups[c] = {'anterior': ant_str, 'nuevo': nvo_str}

                    if hay_cambio:
                        if cambios_cups:
                            cambios_detalle.append({'cups': cups, 'cambios': cambios_cups})

                        set_sql = ', '.join(f'"{c}" = ${i+1}' for i, c in enumerate(update_cols))
                        await conn.execute(
                            f'UPDATE core.t_cups2 SET {set_sql} WHERE id_cups = ${n+1}',
                            *update_vals, cups
                        )
                        actualizados += 1

            except Exception as e:
                logger.warning(f'Error procesando CUPS {cups}: {e}')
                errores += 1

    return {
        'total':                 total,
        'nuevos':                nuevos,
        'actualizados':          actualizados,
        'bajas':                 bajas,
        'errores':               errores,
        'formato':               formato,
        'tipo_fichero':          tipo_fichero,
        'distribuidora':         distribuidora_id,
        'fichero':               file.filename,
        'hoja':                  sheet,
        'avisos':                avisos_total[:100],
        'total_avisos':          len(avisos_total),
        'cambios_detalle':       cambios_detalle[:100],
        'total_cambios_detalle': len(cambios_detalle),
    }