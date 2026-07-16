"""
Seed Batch 3 — Nuevos clientes y actualizaciones

Clientes repetidos (actualizar):
  - FEREZ      — patrones actualizados a 3D (antes tenía S04/S05 con 1D)
  - CELA       — S24 actualizado a >3D (antes era >3D, OK sin cambio)
  - PASTOR     — nuevo cliente real (antes era PASTOR_SABT solo)

Clientes nuevos:
  - VINALESA, MELIANA — mismas creds que Coelca/Talayuelas, estructura 6 subdirectorios
  - EBROFANAS, HIDROBESORA, ALCONERA, BIOSCA, CHULILLA, DIELEC — FTP simple 82.159.192.202
  - SIERRAMAGINA — FTP 82.159.192.202, S26 con >3D (distinto)
  - SIERRAMAGINA_SABT — mismo usuario, directorio SABT
  - HIDROELCARMEN — FTP 82.159.192.202, tamaños mínimos especiales, G01/G02/S06... con >1D
  - HIDROELCARMEN_SABT — mismo usuario, directorio SABT
  - CHULILLA_SABT — mismo usuario, directorio upload/SABT, antigüedad 2D
  - LEIRA — FTP distinto (87.106.228.232), directorio Telegestion/Entrada/Informes
  - BINEFAR — FTP 46.26.87.149:42121, sin cd (raíz), tamaños mínimos
  - PASTOR — FTP 82.159.192.202, directorio /upload (diferente a PASTOR_SABT)
  - CHERA — FTP 185.31.238.178, 3 almacenes (PISCINA, GISBERT, ARRIBA) bajo /128/ x 6 subdirectorios
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import AsyncSessionLocal, engine, Base
from app.services.client_service import ClientService
from app.schemas.schemas import ClientCreate, ClientUpdate, DownloadRuleCreate, FilePatternCreate
from sqlalchemy import select, delete
from app.models.models import Client, DownloadRule, FilePattern


# ─── Helpers ──────────────────────────────────────────────────────────────────

def p(pattern, file_type, subfolder, age=3, size=1, order=0):
    return FilePatternCreate(
        pattern=pattern, file_type=file_type, local_subfolder=subfolder,
        min_age_days=age, min_size_bytes=size, sort_order=order
    )

def std3d():
    """13 patrones estándar: S04..S23 >3D, S24/S26 >1D"""
    return [
        p("*_S04_*","S04","S04",3,1,0), p("*_S05_*","S05","S05",3,1,1),
        p("*_S02_*","S02","S02",3,1,2), p("*_S09_*","S09","S09",3,1,3),
        p("*_G01_*","G01","G01",3,1,4), p("*_G02_*","G02","G02",3,1,5),
        p("*_S06_*","S06","S06",3,1,6), p("*_S12_*","S12","S12",3,1,7),
        p("*_S14_*","S14","S14",3,1,8), p("*_S17_*","S17","S17",3,1,9),
        p("*_S23_*","S23","S23",3,1,10),
        p("*_S24_*","S24","S24",1,1,11), p("*_S26_*","S26","S26",1,1,12),
    ]

def std3d_s26_3d():
    """Igual que std3d pero S26 también >3D (Sierramagina)"""
    return [
        p("*_S04_*","S04","S04",3,1,0), p("*_S05_*","S05","S05",3,1,1),
        p("*_S02_*","S02","S02",3,1,2), p("*_S09_*","S09","S09",3,1,3),
        p("*_G01_*","G01","G01",3,1,4), p("*_G02_*","G02","G02",3,1,5),
        p("*_S06_*","S06","S06",3,1,6), p("*_S12_*","S12","S12",3,1,7),
        p("*_S14_*","S14","S14",3,1,8), p("*_S17_*","S17","S17",3,1,9),
        p("*_S23_*","S23","S23",3,1,10),
        p("*_S24_*","S24","S24",1,1,11), p("*_S26_*","S26","S26",3,1,12),
    ]

def std3d_s24_3d():
    """Igual que std3d pero S24 también >3D (Cela actualizada, Pastor, Dielec)"""
    return [
        p("*_S04_*","S04","S04",3,1,0), p("*_S05_*","S05","S05",3,1,1),
        p("*_S02_*","S02","S02",3,1,2), p("*_S09_*","S09","S09",3,1,3),
        p("*_G01_*","G01","G01",3,1,4), p("*_G02_*","G02","G02",3,1,5),
        p("*_S06_*","S06","S06",3,1,6), p("*_S12_*","S12","S12",3,1,7),
        p("*_S14_*","S14","S14",3,1,8), p("*_S17_*","S17","S17",3,1,9),
        p("*_S23_*","S23","S23",3,1,10),
        p("*_S24_*","S24","S24",3,1,11), p("*_S26_*","S26","S26",1,1,12),
    ]

def hidroelcarmen_patrones():
    """Hidroelcarmen: S04/S05/S02/S09 >3D con tamaños, resto >1D"""
    return [
        p("*_S04_*","S04","S04",3,1500,0), p("*_S05_*","S05","S05",3,800,1),
        p("*_S02_*","S02","S02",3,320,2), p("*_S09_*","S09","S09",3,1,3),
        p("*_G01_*","G01","G01",1,1,4), p("*_G02_*","G02","G02",1,1,5),
        p("*_S06_*","S06","S06",1,1,6), p("*_S12_*","S12","S12",1,1,7),
        p("*_S14_*","S14","S14",1,1,8), p("*_S17_*","S17","S17",1,1,9),
        p("*_S23_*","S23","S23",1,1,10),
        p("*_S24_*","S24","S24",1,1,11), p("*_S26_*","S26","S26",1,1,12),
    ]

def binefar_patrones():
    """Binefar: tamaños mínimos especiales"""
    return [
        p("*_S04_*","S04","S04",3,1500,0), p("*_S05_*","S05","S05",3,800,1),
        p("*_S02_*","S02","S02",3,320,2), p("*_S09_*","S09","S09",3,1,3),
        p("*_G01_*","G01","G01",3,1,4), p("*_G02_*","G02","G02",3,1,5),
        p("*_S06_*","S06","S06",3,1,6), p("*_S12_*","S12","S12",3,1,7),
        p("*_S14_*","S14","S14",3,1,8), p("*_S17_*","S17","S17",3,1,9),
        p("*_S23_*","S23","S23",3,1,10),
        p("*_S24_*","S24","S24",1,1,11), p("*_S26_*","S26","S26",1,1,12),
    ]

def pastor_patrones():
    """Pastor: S24 >3D, S26 >2D"""
    return [
        p("*_S04_*","S04","S04",3,1,0), p("*_S05_*","S05","S05",3,1,1),
        p("*_S02_*","S02","S02",3,1,2), p("*_S09_*","S09","S09",3,1,3),
        p("*_G01_*","G01","G01",3,1,4), p("*_G02_*","G02","G02",3,1,5),
        p("*_S06_*","S06","S06",3,1,6), p("*_S12_*","S12","S12",3,1,7),
        p("*_S14_*","S14","S14",3,1,8), p("*_S17_*","S17","S17",3,1,9),
        p("*_S23_*","S23","S23",3,1,10),
        p("*_S24_*","S24","S24",3,1,11), p("*_S26_*","S26","S26",2,1,12),
    ]

def sabt(age=3):
    return [p("*_*","SABT","SABT",age,1,0)]

def reglas_6sub(base, almacen, sort_base):
    """6 reglas estilo Coelca para un almacén bajo base/almacen"""
    b = f"{base}/{almacen}"
    return [
        DownloadRuleCreate(ftp_directory=b, sort_order=sort_base, active=True,
            notes=f"{almacen} — principal", file_patterns=std3d()),
        DownloadRuleCreate(ftp_directory=f"{b}/saldos", sort_order=sort_base+1, active=True,
            notes=f"{almacen} — saldos",
            file_patterns=[p("*_S05_*","S05","S05",3,1,0)]),
        DownloadRuleCreate(ftp_directory=f"{b}/curvas", sort_order=sort_base+2, active=True,
            notes=f"{almacen} — curvas",
            file_patterns=[p("*_S02_*","S02","S02",3,1,0)]),
        DownloadRuleCreate(ftp_directory=f"{b}/cierres", sort_order=sort_base+3, active=True,
            notes=f"{almacen} — cierres",
            file_patterns=[p("*_S04_*","S04","S04",3,1,0)]),
        DownloadRuleCreate(ftp_directory=f"{b}/inventario", sort_order=sort_base+4, active=True,
            notes=f"{almacen} — inventario",
            file_patterns=[
                p("*_S06_*","S06","S06",3,1,0), p("*_S23_*","S23","S23",3,1,1),
                p("*_G01_*","G01","G01",3,1,2), p("*_G02_*","G02","G02",3,1,3),
                p("*_S12_*","S12","S12",3,1,4),
            ]),
        DownloadRuleCreate(ftp_directory=f"{b}/eventos", sort_order=sort_base+5, active=True,
            notes=f"{almacen} — eventos",
            file_patterns=[p("*_S09_*","S09","S09",3,1,0), p("*_S17_*","S17","S17",3,1,1)]),
    ]


# ─── Almacenes ────────────────────────────────────────────────────────────────

ALMACENES_VINALESA = [
    "ALFARA","CARRAIXET","COLORES1","DELMIG","DEVESA",
    "PARCMOLI","TERSET1","TURRO","SINCRO",
]

ALMACENES_MELIANA = [
    "BENLLOCH","CALVARI","COLON","CORTS","EVALOR",
    "FLEMING","FONT","GARRIGOSA","PAU","PAU2",
]

ALMACENES_CHERA = ["PISCINA","GISBERT","ARRIBA"]


# ─── Actualizaciones ──────────────────────────────────────────────────────────

ACTUALIZACIONES = {
    # FEREZ: actualizar patrones — todos con >3D (S04..S23), S24/S26 >1D
    "FEREZ": {
        "notes": "FTP 82.159.192.202. Patrones actualizados a 3D.",
        "replace_rules": [
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio principal", file_patterns=std3d()),
        ],
    },
    # CELA: S24 cambia a >3D
    "CELA": {
        "notes": "FTP 82.159.192.202. S24 con antigüedad 3D.",
        "replace_rules": [
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio único", file_patterns=std3d_s24_3d()),
        ],
    },
}


# ─── Nuevos clientes ──────────────────────────────────────────────────────────

NUEVOS_CLIENTES = [

    # ── VINALESA — mismas creds ftpalgi, almacenes bajo /212/ ─────────────────
    ClientCreate(
        code="VINALESA", name="Vinalesa",
        notes="FTP 185.31.238.178 mismas creds que Coelca. 9 almacenes bajo /212/ x 6 subdirectorios.",
        ftp_host="185.31.238.178", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftpalgi", ftp_password="PfL1DmeeP",
        ftp_timeout=60, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Vinalesa/Import",
        vpn_required=False, schedule_cron="30 5 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            rule
            for i, almacen in enumerate(ALMACENES_VINALESA)
            for rule in reglas_6sub("/212", almacen, i * 6)
        ],
    ),

    # ── MELIANA — mismas creds ftpalgi, almacenes bajo /226/ ──────────────────
    ClientCreate(
        code="MELIANA", name="Meliana",
        notes="FTP 185.31.238.178 mismas creds que Coelca. 10 almacenes bajo /226/ x 6 subdirectorios.",
        ftp_host="185.31.238.178", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftpalgi", ftp_password="PfL1DmeeP",
        ftp_timeout=60, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Meliana/Import",
        vpn_required=False, schedule_cron="30 5 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            rule
            for i, almacen in enumerate(ALMACENES_MELIANA)
            for rule in reglas_6sub("/226", almacen, i * 6)
        ],
    ),

    # ── CHERA — mismas creds ftpalgi, 3 almacenes bajo /128/ ──────────────────
    ClientCreate(
        code="CHERA", name="Chera",
        notes="FTP 185.31.238.178. 3 almacenes (PISCINA, GISBERT, ARRIBA) bajo /128/ x 6 subdirectorios.",
        ftp_host="185.31.238.178", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftpalgi", ftp_password="PfL1DmeeP",
        ftp_timeout=60, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Chera/Import",
        vpn_required=False, schedule_cron="30 5 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            rule
            for i, almacen in enumerate(ALMACENES_CHERA)
            for rule in reglas_6sub("/128", almacen, i * 6)
        ],
    ),

    # ── EBROFANAS ─────────────────────────────────────────────────────────────
    ClientCreate(
        code="EBROFANAS", name="Ebrofanas",
        notes="FTP 82.159.192.202. Directorio /upload. Patrones estándar 3D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0168", ftp_password="vJ.f7pk7",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Ebrofanas/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio único", file_patterns=std3d()),
        ],
    ),

    # ── HIDROBESORA ───────────────────────────────────────────────────────────
    ClientCreate(
        code="HIDROBESORA", name="Hidrobesora",
        notes="FTP 82.159.192.202. Directorio /upload. Patrones estándar 3D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0635", ftp_password="CahB.0321",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Hidrobesora/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio único", file_patterns=std3d()),
        ],
    ),

    # ── SIERRAMAGINA ──────────────────────────────────────────────────────────
    ClientCreate(
        code="SIERRAMAGINA", name="Sierra Mágina",
        notes="FTP 82.159.192.202. S26 con >3D (distinto al estándar).",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0201", ftp_password="DeeP.8795",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Sierramagina/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio principal — S26 con >3D", file_patterns=std3d_s26_3d()),
        ],
    ),

    # ── SIERRAMAGINA_SABT ─────────────────────────────────────────────────────
    ClientCreate(
        code="SIERRAMAGINA_SABT", name="Sierra Mágina SABT",
        notes="FTP 82.159.192.202 mismo usuario que Sierramagina. Directorio /SABT.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0201", ftp_password="DeeP.8795",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Sierramagina/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/SABT", sort_order=0, active=True,
                notes="Directorio SABT", file_patterns=sabt(3)),
        ],
    ),

    # ── HIDROELCARMEN ─────────────────────────────────────────────────────────
    ClientCreate(
        code="HIDROELCARMEN", name="Hidroeléctrica El Carmen",
        notes="FTP 82.159.192.202. S04/S05/S02 tamaños mínimos, S09/G01..S26 con >1D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0306", ftp_password="RtGf.7851",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Hidroelcarmen/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio principal", file_patterns=hidroelcarmen_patrones()),
        ],
    ),

    # ── HIDROELCARMEN_SABT ────────────────────────────────────────────────────
    ClientCreate(
        code="HIDROELCARMEN_SABT", name="Hidroeléctrica El Carmen SABT",
        notes="FTP 82.159.192.202 mismo usuario que Hidroelcarmen. Directorio /SABT.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0306", ftp_password="RtGf.7851",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Hidroelcarmen/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/SABT", sort_order=0, active=True,
                notes="Directorio SABT", file_patterns=sabt(3)),
        ],
    ),

    # ── ALCONERA ──────────────────────────────────────────────────────────────
    ClientCreate(
        code="ALCONERA", name="Alconera",
        notes="FTP 82.159.192.202. Patrones estándar 3D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0621", ftp_password="aLDa.9764",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Alconera/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio único", file_patterns=std3d()),
        ],
    ),

    # ── BIOSCA ────────────────────────────────────────────────────────────────
    ClientCreate(
        code="BIOSCA", name="Biosca",
        notes="FTP 82.159.192.202. Patrones estándar 3D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0324", ftp_password="cAtW.3568",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Biosca/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio único", file_patterns=std3d()),
        ],
    ),

    # ── CHULILLA ──────────────────────────────────────────────────────────────
    ClientCreate(
        code="CHULILLA", name="Chulilla",
        notes="FTP 82.159.192.202. Patrones estándar 3D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0599", ftp_password="QdSe.1025",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Chulilla/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio principal", file_patterns=std3d()),
        ],
    ),

    # ── CHULILLA_SABT ─────────────────────────────────────────────────────────
    ClientCreate(
        code="CHULILLA_SABT", name="Chulilla SABT",
        notes="FTP 82.159.192.202 mismo usuario que Chulilla. Directorio /upload/SABT. Antigüedad 2D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0599", ftp_password="QdSe.1025",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Chulilla/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload/SABT", sort_order=0, active=True,
                notes="Directorio SABT — antigüedad 2D", file_patterns=sabt(2)),
        ],
    ),

    # ── DIELEC ────────────────────────────────────────────────────────────────
    ClientCreate(
        code="DIELEC", name="Dielec",
        notes="FTP 82.159.192.202. S24 con >3D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0141", ftp_password="jGaD.4125",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Dielec/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio único — S24 con >3D", file_patterns=std3d_s24_3d()),
        ],
    ),

    # ── LEIRA ─────────────────────────────────────────────────────────────────
    ClientCreate(
        code="LEIRA", name="Leira",
        notes="FTP 87.106.228.232 usuario leira. Directorio Telegestion/Entrada/Informes.",
        ftp_host="87.106.228.232", ftp_port=21, ftp_protocol="FTP",
        ftp_user="leira", ftp_password="l3t459a",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Leira/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/Telegestion/Entrada/Informes", sort_order=0, active=True,
                notes="Directorio único Leira", file_patterns=std3d()),
        ],
    ),

    # ── BINEFAR ───────────────────────────────────────────────────────────────
    ClientCreate(
        code="BINEFAR", name="Binefar",
        notes="FTP 46.26.87.149 puerto 42121. Sin cd (descarga desde raíz). Tamaños mínimos especiales.",
        ftp_host="46.26.87.149", ftp_port=42121, ftp_protocol="FTP",
        ftp_user="ftpmaster", ftp_password="Fe70(1ZV86",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Binefar/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/", sort_order=0, active=True,
                notes="Raíz FTP — sin cd", file_patterns=binefar_patrones()),
        ],
    ),

    # ── PASTOR ────────────────────────────────────────────────────────────────
    ClientCreate(
        code="PASTOR", name="Pastor",
        notes="FTP 82.159.192.202. Directorio /upload. S24 >3D, S26 >2D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0267", ftp_password="aXmM.2473",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Pastor/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio principal", file_patterns=pastor_patrones()),
        ],
    ),
]


# ─── Runner ───────────────────────────────────────────────────────────────────

async def seed():
    print("=" * 60)
    print("SEED BATCH 3 — Nuevos clientes y actualizaciones")
    print("=" * 60)

    async with AsyncSessionLocal() as db:

        # ── Actualizaciones ──────────────────────────────────────────────────
        print("\n📝 Actualizando clientes existentes...")
        for code, cambios in ACTUALIZACIONES.items():
            client = await ClientService.get_by_code(db, code)
            if not client:
                print(f"  ⚠️  {code} no encontrado")
                continue

            if "notes" in cambios:
                client.notes = cambios["notes"]

            if "replace_rules" in cambios:
                await db.execute(delete(DownloadRule).where(DownloadRule.client_id == client.id))
                await db.flush()
                for rule_data in cambios["replace_rules"]:
                    from app.services.client_service import ClientService as CS
                    rule_dict = rule_data.model_dump()
                    rule_dict["file_patterns"] = [
                        p.model_dump() if hasattr(p, "model_dump") else p
                        for p in rule_dict.get("file_patterns", [])
                    ]
                    await CS.add_rule(db, client.id, rule_dict)
                print(f"  ✓  {code} — {len(cambios['replace_rules'])} reglas actualizadas")

            await db.commit()

        # ── Nuevos clientes ───────────────────────────────────────────────────
        print("\n➕ Añadiendo nuevos clientes...")
        for client_data in NUEVOS_CLIENTES:
            existing = await ClientService.get_by_code(db, client_data.code)
            if existing:
                print(f"  ⚠️  {client_data.code} ya existe, omitiendo")
                continue
            client = await ClientService.create(db, client_data)
            await db.commit()
            vpn = " [VPN]" if client_data.vpn_required else ""
            print(f"  ✓  {client.code} — {client.name} ({len(client.download_rules)} reglas){vpn}")

    print("\n" + "=" * 60)
    print("Seed batch 3 completado.")
    print("\nResumen:")
    for c in NUEVOS_CLIENTES:
        print(f"  {c.code:25} {c.ftp_host:22} {len(c.download_rules):3} reglas")


if __name__ == "__main__":
    asyncio.run(seed())