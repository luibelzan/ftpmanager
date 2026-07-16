"""
Seed Batch 4 — 4 nuevos clientes

  - HNOSCASTRO   — FTP 82.159.192.202, /upload, patrones estándar 3D
  - MARTINSILVA  — FTP 82.159.192.202, /upload, patrones estándar 3D
  - SOTDECHERA   — FTP 185.31.238.178 (ftpalgi), 2 almacenes bajo /158/ x 6 subdirectorios
  - VILALLER     — FTP promoure.es, 7 directorios simples (sin subdirectorios)
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import AsyncSessionLocal, engine, Base
from app.services.client_service import ClientService
from app.schemas.schemas import ClientCreate, DownloadRuleCreate, FilePatternCreate


def p(pattern, file_type, subfolder, age=3, size=1, order=0):
    return FilePatternCreate(
        pattern=pattern, file_type=file_type, local_subfolder=subfolder,
        min_age_days=age, min_size_bytes=size, sort_order=order
    )

def std3d():
    return [
        p("*_S04_*","S04","S04",3,1,0), p("*_S05_*","S05","S05",3,1,1),
        p("*_S02_*","S02","S02",3,1,2), p("*_S09_*","S09","S09",3,1,3),
        p("*_G01_*","G01","G01",3,1,4), p("*_G02_*","G02","G02",3,1,5),
        p("*_S06_*","S06","S06",3,1,6), p("*_S12_*","S12","S12",3,1,7),
        p("*_S14_*","S14","S14",3,1,8), p("*_S17_*","S17","S17",3,1,9),
        p("*_S23_*","S23","S23",3,1,10),
        p("*_S24_*","S24","S24",1,1,11), p("*_S26_*","S26","S26",1,1,12),
    ]

def reglas_6sub(base, almacen, sort_base):
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


NUEVOS_CLIENTES = [

    # ── HNOSCASTRO ────────────────────────────────────────────────────────────
    ClientCreate(
        code="HNOSCASTRO", name="Hermanos Castro",
        notes="FTP 82.159.192.202. Directorio /upload. Patrones estándar 3D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0238", ftp_password="rYzU.5724",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Hnoscastro/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio único", file_patterns=std3d()),
        ],
    ),

    # ── MARTINSILVA ───────────────────────────────────────────────────────────
    ClientCreate(
        code="MARTINSILVA", name="Martín Silva",
        notes="FTP 82.159.192.202. Directorio /upload. Patrones estándar 3D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0278", ftp_password="dSEw.5032",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Martinsilva/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio único", file_patterns=std3d()),
        ],
    ),

    # ── SOTDECHERA — 2 almacenes bajo /158/ x 6 subdirectorios ───────────────
    ClientCreate(
        code="SOTDECHERA", name="Sot de Chera",
        notes="FTP 185.31.238.178 mismas creds que Coelca. 2 almacenes (RINCON, RIO) bajo /158/ x 6 subdirectorios.",
        ftp_host="185.31.238.178", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftpalgi", ftp_password="PfL1DmeeP",
        ftp_timeout=60, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Sotdechera/Import",
        vpn_required=False, schedule_cron="30 5 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            *reglas_6sub("/158", "RINCON", 0),
            *reglas_6sub("/158", "RIO", 6),
        ],
    ),

    # ── VILALLER — FTP promoure.es, 7 directorios simples ────────────────────
    # Nota: usuario contiene @ — es jairo@promoure.es, password mallorca115
    ClientCreate(
        code="VILALLER", name="Vilaller",
        notes="FTP promoure.es usuario jairo@promoure.es. 7 directorios sin subdirectorios.",
        ftp_host="promoure.es", ftp_port=21, ftp_protocol="FTP",
        ftp_user="jairo@promoure.es", ftp_password="mallorca115",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Vilaller/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/trinquet",   sort_order=0, active=True, notes="Trinquet",   file_patterns=std3d()),
            DownloadRuleCreate(ftp_directory="/escamps",    sort_order=1, active=True, notes="Escamps",    file_patterns=std3d()),
            DownloadRuleCreate(ftp_directory="/edar",       sort_order=2, active=True, notes="Edar",       file_patterns=std3d()),
            DownloadRuleCreate(ftp_directory="/montsant",   sort_order=3, active=True, notes="Montsant",   file_patterns=std3d()),
            DownloadRuleCreate(ftp_directory="/cooperativa",sort_order=4, active=True, notes="Cooperativa",file_patterns=std3d()),
            DownloadRuleCreate(ftp_directory="/upload",     sort_order=5, active=True, notes="Upload",     file_patterns=std3d()),
            DownloadRuleCreate(ftp_directory="/pobminero",  sort_order=6, active=True, notes="Pobminero",  file_patterns=std3d()),
            DownloadRuleCreate(ftp_directory="/pueblo",     sort_order=7, active=True, notes="Pueblo",     file_patterns=std3d()),
        ],
    ),
]


async def seed():
    print("=" * 60)
    print("SEED BATCH 4 — 4 nuevos clientes")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        print("\n➕ Añadiendo clientes...")
        for client_data in NUEVOS_CLIENTES:
            existing = await ClientService.get_by_code(db, client_data.code)
            if existing:
                print(f"  ⚠️  {client_data.code} ya existe, omitiendo")
                continue
            client = await ClientService.create(db, client_data)
            await db.commit()
            print(f"  ✓  {client.code} — {client.name} ({len(client.download_rules)} reglas)")

    print("\nSeed batch 4 completado.")


if __name__ == "__main__":
    asyncio.run(seed())