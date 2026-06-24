"""
Script de carga inicial de los 3 clientes de prueba.

Clientes:
  1. FEREZ      — FTP simple, un directorio, sin VPN
  2. VARGAS     — FTP con VPN OpenVPN, múltiples directorios
  3. GARCIA     — SFTP, un directorio, sin VPN

Uso:
  python scripts/seed_clients.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import AsyncSessionLocal, engine, Base
from app.services.client_service import ClientService
from app.schemas.schemas import ClientCreate, DownloadRuleCreate, FilePatternCreate


# ─── Definición de los 3 clientes ────────────────────────────────────────────

CLIENTS = [

    # ── 1. FEREZ — FTP simple ─────────────────────────────────────────────────
    # Script .bat original:
    #   open ftp://ftp_0132:iCLq.0573@82.159.192.202
    #   cd upload
    #   get *_S04_*>1D>=1  C:\GD\Distribuidoras\Ferez\Import\S04\
    #   get *_S05_*>1D>=1  C:\GD\Distribuidoras\Ferez\Import\S05\
    ClientCreate(
        code="FEREZ",
        name="Distribuidora Ferez S.L.",
        notes="Cliente simple FTP. Un solo directorio /upload con S04 y S05.",
        ftp_host="82.159.192.202",
        ftp_port=21,
        ftp_protocol="FTP",
        ftp_user="ftp_0132",
        ftp_password="iCLq.0573",
        ftp_timeout=30,
        ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Ferez/Import",
        vpn_required=False,
        schedule_cron="0 6 * * 1-6",     # Lunes-sábado a las 06:00
        schedule_active=True,
        retry_attempts=3,
        retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(
                ftp_directory="/upload",
                sort_order=0,
                active=True,
                notes="Directorio principal de Ferez",
                file_patterns=[
                    FilePatternCreate(
                        pattern="*_S04_*",
                        file_type="S04",
                        local_subfolder="S04",
                        min_age_days=1,
                        min_size_bytes=1,
                        sort_order=0,
                    ),
                    FilePatternCreate(
                        pattern="*_S05_*",
                        file_type="S05",
                        local_subfolder="S05",
                        min_age_days=1,
                        min_size_bytes=1,
                        sort_order=1,
                    ),
                ],
            )
        ],
    ),

    # ── 2. VARGAS — FTP + VPN, múltiples directorios ─────────────────────────
    # Script .bat original:
    #   Directorio 1: /Vargas/VA_Penillar/Upload   (patrones >3D y >1D)
    #   Directorio 2: /Vargas/VA_Poligono/Upload   (mismos patrones)
    ClientCreate(
        code="VARGAS",
        name="Distribuciones Vargas e Hijos S.L.",
        notes="Requiere VPN OpenVPN. Dos subdirectorios: Penillar y Poligono.",
        ftp_host="10.10.5.20",           # IP interna accesible vía VPN
        ftp_port=21,
        ftp_protocol="FTP",
        ftp_user="vargas_ftp",
        ftp_password="VaRg4s_2024!",
        ftp_timeout=45,
        ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Vargas/Import",
        vpn_required=True,
        vpn_config_file="vargas.ovpn",   # fichero en OPENVPN_CONFIG_DIR
        schedule_cron="30 5 * * 1-6",    # Lunes-sábado a las 05:30
        schedule_active=True,
        retry_attempts=3,
        retry_delay_seconds=600,          # Más tiempo por la VPN
        download_rules=[
            DownloadRuleCreate(
                ftp_directory="/Vargas/VA_Penillar/Upload",
                sort_order=0,
                active=True,
                notes="Almacén Penillar — patrones con antigüedad mixta",
                file_patterns=[
                    FilePatternCreate(pattern="*_S04_*", file_type="S04", local_subfolder="S04", min_age_days=3, min_size_bytes=1, sort_order=0),
                    FilePatternCreate(pattern="*_S05_*", file_type="S05", local_subfolder="S05", min_age_days=3, min_size_bytes=1, sort_order=1),
                    FilePatternCreate(pattern="*_S02_*", file_type="S02", local_subfolder="S02", min_age_days=3, min_size_bytes=1, sort_order=2),
                    FilePatternCreate(pattern="*_S09_*", file_type="S09", local_subfolder="S09", min_age_days=3, min_size_bytes=1, sort_order=3),
                    FilePatternCreate(pattern="*_G01_*", file_type="G01", local_subfolder="G01", min_age_days=3, min_size_bytes=1, sort_order=4),
                    FilePatternCreate(pattern="*_G02_*", file_type="G02", local_subfolder="G02", min_age_days=3, min_size_bytes=1, sort_order=5),
                    FilePatternCreate(pattern="*_S06_*", file_type="S06", local_subfolder="S06", min_age_days=3, min_size_bytes=1, sort_order=6),
                    FilePatternCreate(pattern="*_S12_*", file_type="S12", local_subfolder="S12", min_age_days=3, min_size_bytes=1, sort_order=7),
                    FilePatternCreate(pattern="*_S14_*", file_type="S14", local_subfolder="S14", min_age_days=3, min_size_bytes=1, sort_order=8),
                    FilePatternCreate(pattern="*_S17_*", file_type="S17", local_subfolder="S17", min_age_days=3, min_size_bytes=1, sort_order=9),
                    FilePatternCreate(pattern="*_S23_*", file_type="S23", local_subfolder="S23", min_age_days=3, min_size_bytes=1, sort_order=10),
                    FilePatternCreate(pattern="*_S24_*", file_type="S24", local_subfolder="S24", min_age_days=1, min_size_bytes=1, sort_order=11),
                    FilePatternCreate(pattern="*_S26_*", file_type="S26", local_subfolder="S26", min_age_days=1, min_size_bytes=1, sort_order=12),
                ],
            ),
            DownloadRuleCreate(
                ftp_directory="/Vargas/VA_Poligono/Upload",
                sort_order=1,
                active=True,
                notes="Almacén Polígono — mismos tipos de fichero que Penillar",
                file_patterns=[
                    FilePatternCreate(pattern="*_S04_*", file_type="S04", local_subfolder="S04", min_age_days=3, min_size_bytes=1, sort_order=0),
                    FilePatternCreate(pattern="*_S05_*", file_type="S05", local_subfolder="S05", min_age_days=3, min_size_bytes=1, sort_order=1),
                    FilePatternCreate(pattern="*_S02_*", file_type="S02", local_subfolder="S02", min_age_days=3, min_size_bytes=1, sort_order=2),
                    FilePatternCreate(pattern="*_S09_*", file_type="S09", local_subfolder="S09", min_age_days=3, min_size_bytes=1, sort_order=3),
                    FilePatternCreate(pattern="*_G01_*", file_type="G01", local_subfolder="G01", min_age_days=3, min_size_bytes=1, sort_order=4),
                    FilePatternCreate(pattern="*_G02_*", file_type="G02", local_subfolder="G02", min_age_days=3, min_size_bytes=1, sort_order=5),
                    FilePatternCreate(pattern="*_S06_*", file_type="S06", local_subfolder="S06", min_age_days=3, min_size_bytes=1, sort_order=6),
                    FilePatternCreate(pattern="*_S12_*", file_type="S12", local_subfolder="S12", min_age_days=3, min_size_bytes=1, sort_order=7),
                    FilePatternCreate(pattern="*_S14_*", file_type="S14", local_subfolder="S14", min_age_days=3, min_size_bytes=1, sort_order=8),
                    FilePatternCreate(pattern="*_S17_*", file_type="S17", local_subfolder="S17", min_age_days=3, min_size_bytes=1, sort_order=9),
                    FilePatternCreate(pattern="*_S23_*", file_type="S23", local_subfolder="S23", min_age_days=3, min_size_bytes=1, sort_order=10),
                    FilePatternCreate(pattern="*_S24_*", file_type="S24", local_subfolder="S24", min_age_days=1, min_size_bytes=1, sort_order=11),
                    FilePatternCreate(pattern="*_S26_*", file_type="S26", local_subfolder="S26", min_age_days=1, min_size_bytes=1, sort_order=12),
                ],
            ),
        ],
    ),

    # ── 3. GARCIA — SFTP simple ────────────────────────────────────────────────
    ClientCreate(
        code="GARCIA",
        name="Distribuciones García Hermanos",
        notes="Conexión SFTP puerto 22. Un directorio /datos/salida.",
        ftp_host="ftp.garcia-dist.es",
        ftp_port=22,
        ftp_protocol="SFTP",
        ftp_user="garcia_sftp",
        ftp_password="G4rc14!2024",
        ftp_timeout=30,
        ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Garcia/Import",
        vpn_required=False,
        schedule_cron="15 6 * * 1-6",   # Lunes-sábado a las 06:15
        schedule_active=True,
        retry_attempts=3,
        retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(
                ftp_directory="/datos/salida",
                sort_order=0,
                active=True,
                notes="Directorio único de García",
                file_patterns=[
                    FilePatternCreate(pattern="*_S04_*", file_type="S04", local_subfolder="S04", min_age_days=1, min_size_bytes=1, sort_order=0),
                    FilePatternCreate(pattern="*_S05_*", file_type="S05", local_subfolder="S05", min_age_days=1, min_size_bytes=1, sort_order=1),
                    FilePatternCreate(pattern="*_G01_*", file_type="G01", local_subfolder="G01", min_age_days=1, min_size_bytes=1, sort_order=2),
                ],
            )
        ],
    ),
]


# ─── Runner ───────────────────────────────────────────────────────────────────

async def seed():
    print("Creando tablas...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Cargando clientes iniciales...")
    async with AsyncSessionLocal() as db:
        for client_data in CLIENTS:
            existing = await ClientService.get_by_code(db, client_data.code)
            if existing:
                print(f"  ⚠️  {client_data.code} ya existe, omitiendo")
                continue
            client = await ClientService.create(db, client_data)
            await db.commit()
            print(f"  ✓  {client.code} — {client.name}")
            print(f"     Reglas: {len(client.download_rules)}")
            for rule in client.download_rules:
                print(f"       · {rule.ftp_directory} ({len(rule.file_patterns)} patrones)")

    print("\nSeed completado.")
    print("\nResumen de schedules:")
    for c in CLIENTS:
        vpn_tag = " [VPN]" if c.vpn_required else ""
        print(f"  {c.code:10} {c.schedule_cron:20} {c.ftp_protocol}{vpn_tag}")


if __name__ == "__main__":
    asyncio.run(seed())
