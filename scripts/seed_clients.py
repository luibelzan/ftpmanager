"""
Script de carga inicial de clientes.

Clientes:
  1. FEREZ       — FTP simple, un directorio, sin VPN
  2. VARGAS      — FTP con VPN OpenVPN, múltiples directorios
  3. GARCIA      — SFTP, un directorio, sin VPN (datos de ejemplo)
  4. CELA        — FTP simple, un directorio, sin VPN
  5. SANTACLARA  — FTP, 3 directorios, CON VPN
  6. COELCA      — FTP, 10 almacenes x 6 directorios, sin VPN

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


# ─── Patrones comunes ─────────────────────────────────────────────────────────

def patrones_3d():
    return [
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
    ]


def patrones_1d():
    return [
        FilePatternCreate(pattern="*_S04_*", file_type="S04", local_subfolder="S04", min_age_days=1, min_size_bytes=1, sort_order=0),
        FilePatternCreate(pattern="*_S05_*", file_type="S05", local_subfolder="S05", min_age_days=1, min_size_bytes=1, sort_order=1),
        FilePatternCreate(pattern="*_S02_*", file_type="S02", local_subfolder="S02", min_age_days=1, min_size_bytes=1, sort_order=2),
        FilePatternCreate(pattern="*_S09_*", file_type="S09", local_subfolder="S09", min_age_days=1, min_size_bytes=1, sort_order=3),
        FilePatternCreate(pattern="*_G01_*", file_type="G01", local_subfolder="G01", min_age_days=1, min_size_bytes=1, sort_order=4),
        FilePatternCreate(pattern="*_G02_*", file_type="G02", local_subfolder="G02", min_age_days=1, min_size_bytes=1, sort_order=5),
        FilePatternCreate(pattern="*_S06_*", file_type="S06", local_subfolder="S06", min_age_days=1, min_size_bytes=1, sort_order=6),
        FilePatternCreate(pattern="*_S12_*", file_type="S12", local_subfolder="S12", min_age_days=1, min_size_bytes=1, sort_order=7),
        FilePatternCreate(pattern="*_S14_*", file_type="S14", local_subfolder="S14", min_age_days=1, min_size_bytes=1, sort_order=8),
        FilePatternCreate(pattern="*_S17_*", file_type="S17", local_subfolder="S17", min_age_days=1, min_size_bytes=1, sort_order=9),
        FilePatternCreate(pattern="*_S23_*", file_type="S23", local_subfolder="S23", min_age_days=1, min_size_bytes=1, sort_order=10),
        FilePatternCreate(pattern="*_S24_*", file_type="S24", local_subfolder="S24", min_age_days=1, min_size_bytes=1, sort_order=11),
        FilePatternCreate(pattern="*_S26_*", file_type="S26", local_subfolder="S26", min_age_days=1, min_size_bytes=1, sort_order=12),
    ]


def reglas_coelca(almacen: str, sort_base: int) -> list[DownloadRuleCreate]:
    base = f"/135/{almacen}"
    return [
        DownloadRuleCreate(
            ftp_directory=base,
            sort_order=sort_base,
            active=True,
            notes=f"{almacen} — directorio principal",
            file_patterns=patrones_3d(),
        ),
        DownloadRuleCreate(
            ftp_directory=f"{base}/saldos",
            sort_order=sort_base + 1,
            active=True,
            notes=f"{almacen} — saldos",
            file_patterns=[
                FilePatternCreate(pattern="*_S05_*", file_type="S05", local_subfolder="S05", min_age_days=3, min_size_bytes=1, sort_order=0),
            ],
        ),
        DownloadRuleCreate(
            ftp_directory=f"{base}/curvas",
            sort_order=sort_base + 2,
            active=True,
            notes=f"{almacen} — curvas",
            file_patterns=[
                FilePatternCreate(pattern="*_S02_*", file_type="S02", local_subfolder="S02", min_age_days=3, min_size_bytes=1, sort_order=0),
            ],
        ),
        DownloadRuleCreate(
            ftp_directory=f"{base}/cierres",
            sort_order=sort_base + 3,
            active=True,
            notes=f"{almacen} — cierres",
            file_patterns=[
                FilePatternCreate(pattern="*_S04_*", file_type="S04", local_subfolder="S04", min_age_days=3, min_size_bytes=1, sort_order=0),
            ],
        ),
        DownloadRuleCreate(
            ftp_directory=f"{base}/inventario",
            sort_order=sort_base + 4,
            active=True,
            notes=f"{almacen} — inventario",
            file_patterns=[
                FilePatternCreate(pattern="*_S06_*", file_type="S06", local_subfolder="S06", min_age_days=3, min_size_bytes=1, sort_order=0),
                FilePatternCreate(pattern="*_S23_*", file_type="S23", local_subfolder="S23", min_age_days=3, min_size_bytes=1, sort_order=1),
                FilePatternCreate(pattern="*_G01_*", file_type="G01", local_subfolder="G01", min_age_days=3, min_size_bytes=1, sort_order=2),
                FilePatternCreate(pattern="*_G02_*", file_type="G02", local_subfolder="G02", min_age_days=3, min_size_bytes=1, sort_order=3),
                FilePatternCreate(pattern="*_S12_*", file_type="S12", local_subfolder="S12", min_age_days=3, min_size_bytes=1, sort_order=4),
            ],
        ),
        DownloadRuleCreate(
            ftp_directory=f"{base}/eventos",
            sort_order=sort_base + 5,
            active=True,
            notes=f"{almacen} — eventos",
            file_patterns=[
                FilePatternCreate(pattern="*_S09_*", file_type="S09", local_subfolder="S09", min_age_days=3, min_size_bytes=1, sort_order=0),
                FilePatternCreate(pattern="*_S17_*", file_type="S17", local_subfolder="S17", min_age_days=3, min_size_bytes=1, sort_order=1),
            ],
        ),
    ]


# ─── Almacenes Coelca ─────────────────────────────────────────────────────────

ALMACENES_COELCA = [
    "OLIVERAL", "FONTETA", "BALES", "SIURANA",
    "TREMOLAR", "VAQUES", "ARBOLEDA", "EUROPA",
    "SALEM", "SANTONIO",
]


# ─── Definición de todos los clientes ────────────────────────────────────────

CLIENTS = [

    # ── 1. FEREZ ──────────────────────────────────────────────────────────────
    ClientCreate(
        code="FEREZ",
        name="Distribuidora Ferez S.L.",
        notes="FTP simple. Un directorio /upload con S04 y S05.",
        ftp_host="82.159.192.202",
        ftp_port=21,
        ftp_protocol="FTP",
        ftp_user="ftp_0132",
        ftp_password="iCLq.0573",
        ftp_timeout=30,
        ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Ferez/Import",
        vpn_required=False,
        schedule_cron="0 6 * * 1-6",
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
                    FilePatternCreate(pattern="*_S04_*", file_type="S04", local_subfolder="S04", min_age_days=1, min_size_bytes=1, sort_order=0),
                    FilePatternCreate(pattern="*_S05_*", file_type="S05", local_subfolder="S05", min_age_days=1, min_size_bytes=1, sort_order=1),
                ],
            ),
        ],
    ),

    # ── 2. VARGAS — FTP + VPN ─────────────────────────────────────────────────
    ClientCreate(
        code="VARGAS",
        name="Distribuciones Vargas e Hijos S.L.",
        notes="Requiere VPN OpenVPN. Dos subdirectorios: Penillar y Poligono.",
        ftp_host="10.10.5.20",
        ftp_port=21,
        ftp_protocol="FTP",
        ftp_user="vargas_ftp",
        ftp_password="VaRg4s_2024!",
        ftp_timeout=45,
        ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Vargas/Import",
        vpn_required=True,
        vpn_config_file="vargas.ovpn",
        schedule_cron="30 5 * * 1-6",
        schedule_active=True,
        retry_attempts=3,
        retry_delay_seconds=600,
        download_rules=[
            DownloadRuleCreate(
                ftp_directory="/Vargas/VA_Penillar/Upload",
                sort_order=0,
                active=True,
                notes="Almacén Penillar",
                file_patterns=patrones_3d(),
            ),
            DownloadRuleCreate(
                ftp_directory="/Vargas/VA_Poligono/Upload",
                sort_order=1,
                active=True,
                notes="Almacén Polígono",
                file_patterns=patrones_3d(),
            ),
        ],
    ),

    # ── 3. GARCIA — SFTP (datos de ejemplo, actualizar credenciales reales) ───
    ClientCreate(
        code="GARCIA",
        name="Distribuciones García Hermanos",
        notes="Conexión SFTP puerto 22. Actualizar host y credenciales reales.",
        ftp_host="ftp.garcia-dist.es",
        ftp_port=22,
        ftp_protocol="SFTP",
        ftp_user="garcia_sftp",
        ftp_password="G4rc14!2024",
        ftp_timeout=30,
        ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Garcia/Import",
        vpn_required=False,
        schedule_cron="15 6 * * 1-6",
        schedule_active=False,
        retry_attempts=3,
        retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(
                ftp_directory="/datos/salida",
                sort_order=0,
                active=True,
                notes="Directorio único de García",
                file_patterns=patrones_1d(),
            ),
        ],
    ),

    # ── 4. CELA — FTP simple ──────────────────────────────────────────────────
    ClientCreate(
        code="CELA",
        name="Distribuidora Cela",
        notes="FTP simple. Un directorio /upload. Transferencia ASCII.",
        ftp_host="82.159.192.202",
        ftp_port=21,
        ftp_protocol="FTP",
        ftp_user="ftp_0412",
        ftp_password="nJFd.6458",
        ftp_timeout=30,
        ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Cela/Import",
        vpn_required=False,
        schedule_cron="0 6 * * 1-6",
        schedule_active=True,
        retry_attempts=3,
        retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(
                ftp_directory="/upload",
                sort_order=0,
                active=True,
                notes="Directorio único de Cela",
                file_patterns=patrones_3d(),
            ),
        ],
    ),

    # ── 5. SANTACLARA — FTP + VPN, 3 directorios ─────────────────────────────
    ClientCreate(
        code="SANTACLARA",
        name="Distribuidora Santa Clara",
        notes="Requiere VPN. IP interna 192.168.127.150. 3 directorios.",
        ftp_host="192.168.127.150",
        ftp_port=21,
        ftp_protocol="FTP",
        ftp_user="celnet",
        ftp_password="Cn1720$%",
        ftp_timeout=45,
        ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Santaclara/Import",
        vpn_required=True,
        vpn_config_file="santaclara.ovpn",
        schedule_cron="0 6 * * 1-6",
        schedule_active=True,
        retry_attempts=3,
        retry_delay_seconds=600,
        download_rules=[
            DownloadRuleCreate(
                ftp_directory="/upload",
                sort_order=0,
                active=True,
                notes="Directorio principal",
                file_patterns=patrones_3d(),
            ),
            DownloadRuleCreate(
                ftp_directory="/202606",
                sort_order=1,
                active=True,
                notes="Directorio mensual 202606 — actualizar cada mes",
                file_patterns=patrones_3d(),
            ),
            DownloadRuleCreate(
                ftp_directory="/error",
                sort_order=2,
                active=True,
                notes="Directorio de errores — solo S26",
                file_patterns=[
                    FilePatternCreate(pattern="*_S26_*", file_type="S26", local_subfolder="S26", min_age_days=1, min_size_bytes=1, sort_order=0),
                ],
            ),
        ],
    ),

    # ── 6. COELCA — FTP, 10 almacenes x 6 directorios ────────────────────────
    ClientCreate(
        code="COELCA",
        name="Coelca",
        notes="FTP con 10 almacenes bajo /135/. Cada almacén tiene 6 subdirectorios.",
        ftp_host="185.31.238.178",
        ftp_port=21,
        ftp_protocol="FTP",
        ftp_user="ftpalgi",
        ftp_password="PfL1DmeeP",
        ftp_timeout=60,
        ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Coelca/Import",
        vpn_required=False,
        schedule_cron="30 5 * * 1-6",
        schedule_active=True,
        retry_attempts=3,
        retry_delay_seconds=300,
        download_rules=[
            rule
            for i, almacen in enumerate(ALMACENES_COELCA)
            for rule in reglas_coelca(almacen, sort_base=i * 6)
        ],
    ),
]


# ─── Runner ───────────────────────────────────────────────────────────────────

async def seed():
    print("Creando tablas si no existen...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("\nCargando clientes...")
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
    print("\nResumen:")
    for c in CLIENTS:
        vpn_tag = " [VPN]" if c.vpn_required else ""
        active_tag = "" if c.schedule_active else " [INACTIVO]"
        rules = len(c.download_rules)
        print(f"  {c.code:12} {c.schedule_cron:20} {rules:3} reglas  {c.ftp_protocol}{vpn_tag}{active_tag}")


if __name__ == "__main__":
    asyncio.run(seed())