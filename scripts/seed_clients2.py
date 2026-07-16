"""
Script de actualización y carga de nuevos clientes - Batch 2

Clientes actualizados:
  - VARGAS      — nuevas credenciales, host y 15 almacenes
  - SANTACLARA  — directorio mensual actualizado a /202607

Clientes nuevos:
  - SANPEDRO, MOLARES, MERCEDES, LAPROHIDA, ALVAROBENITO
  - HELIODORO, HELIODORO_SABT, ACSI (2 FTP), MERCEDES_SABT (7 FTP)
  - SANTACLARA_SABT, PASTOR_SABT, LEANDRO, ALBORENSE, CERRAJON, TALAYUELAS
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import AsyncSessionLocal, engine, Base
from app.services.client_service import ClientService
from app.schemas.schemas import ClientCreate, ClientUpdate, DownloadRuleCreate, FilePatternCreate
from sqlalchemy import select, delete
from app.models.models import Client, DownloadRule


# ─── Helpers de patrones ──────────────────────────────────────────────────────

def pat(pattern, file_type, subfolder, age=3, size=1, order=0):
    return FilePatternCreate(
        pattern=pattern, file_type=file_type, local_subfolder=subfolder,
        min_age_days=age, min_size_bytes=size, sort_order=order
    )

def patrones_std_3d(base_path=""):
    """13 patrones estándar >3D (S24 y S26 con >1D)"""
    return [
        pat("*_S04_*", "S04", "S04", 3, 1, 0),
        pat("*_S05_*", "S05", "S05", 3, 1, 1),
        pat("*_S02_*", "S02", "S02", 3, 1, 2),
        pat("*_S09_*", "S09", "S09", 3, 1, 3),
        pat("*_G01_*", "G01", "G01", 3, 1, 4),
        pat("*_G02_*", "G02", "G02", 3, 1, 5),
        pat("*_S06_*", "S06", "S06", 3, 1, 6),
        pat("*_S12_*", "S12", "S12", 3, 1, 7),
        pat("*_S14_*", "S14", "S14", 3, 1, 8),
        pat("*_S17_*", "S17", "S17", 3, 1, 9),
        pat("*_S23_*", "S23", "S23", 3, 1, 10),
        pat("*_S24_*", "S24", "S24", 1, 1, 11),
        pat("*_S26_*", "S26", "S26", 1, 1, 12),
    ]

def patrones_std_2d():
    """Patrones con >2D (Leandro, Alborense)"""
    return [
        pat("*_S04_*", "S04", "S04", 2, 1, 0),
        pat("*_S05_*", "S05", "S05", 2, 1, 1),
        pat("*_S02_*", "S02", "S02", 2, 1, 2),
        pat("*_S09_*", "S09", "S09", 2, 1, 3),
        pat("*_G01_*", "G01", "G01", 2, 1, 4),
        pat("*_G02_*", "G02", "G02", 2, 1, 5),
        pat("*_S06_*", "S06", "S06", 2, 1, 6),
        pat("*_S12_*", "S12", "S12", 2, 1, 7),
        pat("*_S14_*", "S14", "S14", 2, 1, 8),
        pat("*_S17_*", "S17", "S17", 2, 1, 9),
        pat("*_S23_*", "S23", "S23", 2, 1, 10),
        pat("*_S24_*", "S24", "S24", 1, 1, 11),
        pat("*_S26_*", "S26", "S26", 1, 1, 12),
    ]

def patrones_mercedes():
    """Mercedes tiene tamaños mínimos especiales"""
    return [
        pat("*_S17_*", "S17", "S17", 3, 1, 0),
        pat("*_S04_*", "S04", "S04", 3, 1500, 1),
        pat("*_S05_*", "S05", "S05", 3, 800, 2),
        pat("*_S02_*", "S02", "S02", 3, 320, 3),
        pat("*_S09_*", "S09", "S09", 3, 1, 4),
        pat("*_G01_*", "G01", "G01", 3, 1, 5),
        pat("*_G02_*", "G02", "G02", 3, 1, 6),
        pat("*_S06_*", "S06", "S06", 3, 1, 7),
        pat("*_S12_*", "S12", "S12", 3, 1, 8),
        pat("*_S14_*", "S14", "S14", 3, 1, 9),
        pat("*_S23_*", "S23", "S23", 3, 1, 10),
        pat("*_S24_*", "S24", "S24", 1, 1, 11),
        pat("*_S26_*", "S26", "S26", 1, 1, 12),
    ]

def patrones_laprohida():
    """Laprohida también tiene tamaños mínimos especiales"""
    return [
        pat("*_S04_*", "S04", "S04", 3, 1500, 0),
        pat("*_S05_*", "S05", "S05", 3, 800, 1),
        pat("*_S02_*", "S02", "S02", 3, 320, 2),
        pat("*_S09_*", "S09", "S09", 3, 1, 3),
        pat("*_G01_*", "G01", "G01", 3, 1, 4),
        pat("*_G02_*", "G02", "G02", 3, 1, 5),
        pat("*_S06_*", "S06", "S06", 3, 1, 6),
        pat("*_S12_*", "S12", "S12", 3, 1, 7),
        pat("*_S14_*", "S14", "S14", 3, 1, 8),
        pat("*_S17_*", "S17", "S17", 3, 1, 9),
        pat("*_S23_*", "S23", "S23", 3, 1, 10),
        pat("*_S24_*", "S24", "S24", 1, 1, 11),
        pat("*_S26_*", "S26", "S26", 1, 1, 12),
    ]

def patrones_heliodoro():
    """Heliodoro tiene prefijo CIR4621748247 en todos los patrones"""
    return [
        pat("CIR4621748247*_S04_*", "S04", "S04", 3, 1, 0),
        pat("CIR4621748247*_S05_*", "S05", "S05", 3, 1, 1),
        pat("CIR4621748247*_S02_*", "S02", "S02", 3, 1, 2),
        pat("CIR4621748247*_S09_*", "S09", "S09", 3, 1, 3),
        pat("CIR4621748247*_G01_*", "G01", "G01", 3, 1, 4),
        pat("CIR4621748247*_G02_*", "G02", "G02", 3, 1, 5),
        pat("CIR4621748247*_S06_*", "S06", "S06", 3, 1, 6),
        pat("CIR4621748247*_S12_*", "S12", "S12", 3, 1, 7),
        pat("CIR4621748247*_S14_*", "S14", "S14", 3, 1, 8),
        pat("CIR4621748247*_S17_*", "S17", "S17", 3, 1, 9),
        pat("CIR4621748247*_S23_*", "S23", "S23", 3, 1, 10),
        pat("CIR4621748247*_S24_*", "S24", "S24", 1, 1, 11),
        pat("CIR4621748247*_S26_*", "S26", "S26", 1, 1, 12),
    ]

def patron_sabt(age=3):
    """Patrón comodín para ficheros SABT"""
    return [pat("*_*", "SABT", "SABT", age, 1, 0)]

def reglas_coelca_style(base_prefix, almacen, sort_base):
    """Genera 6 reglas estilo Coelca/Talayuelas para un almacén"""
    base = f"/{base_prefix}/{almacen}"
    return [
        DownloadRuleCreate(ftp_directory=base, sort_order=sort_base, active=True,
            notes=f"{almacen} — principal", file_patterns=patrones_std_3d()),
        DownloadRuleCreate(ftp_directory=f"{base}/saldos", sort_order=sort_base+1, active=True,
            notes=f"{almacen} — saldos",
            file_patterns=[pat("*_S05_*","S05","S05",3,1,0)]),
        DownloadRuleCreate(ftp_directory=f"{base}/curvas", sort_order=sort_base+2, active=True,
            notes=f"{almacen} — curvas",
            file_patterns=[pat("*_S02_*","S02","S02",3,1,0)]),
        DownloadRuleCreate(ftp_directory=f"{base}/cierres", sort_order=sort_base+3, active=True,
            notes=f"{almacen} — cierres",
            file_patterns=[pat("*_S04_*","S04","S04",3,1,0)]),
        DownloadRuleCreate(ftp_directory=f"{base}/inventario", sort_order=sort_base+4, active=True,
            notes=f"{almacen} — inventario",
            file_patterns=[
                pat("*_S06_*","S06","S06",3,1,0), pat("*_S23_*","S23","S23",3,1,1),
                pat("*_G01_*","G01","G01",3,1,2), pat("*_G02_*","G02","G02",3,1,3),
                pat("*_S12_*","S12","S12",3,1,4),
            ]),
        DownloadRuleCreate(ftp_directory=f"{base}/eventos", sort_order=sort_base+5, active=True,
            notes=f"{almacen} — eventos",
            file_patterns=[pat("*_S09_*","S09","S09",3,1,0), pat("*_S17_*","S17","S17",3,1,1)]),
    ]


# ─── Almacenes ────────────────────────────────────────────────────────────────

ALMACENES_VARGAS = [
    "VA_Agustin","VA_Angela","VA_Bruno","VA_Candil","VA_Cesar",
    "VA_Cuartel","VA_Josefa","VA_Lepanto","VA_Lopez","VA_Minas",
    "VA_Otilia","VA_Penillar","VA_Poligono","VA_Repetidor","VA_Sanguijolero",
    "VA_Toledo","VA_Torronteras","VA_Verbena","VA_Virgen",
]

ALMACENES_TALAYUELAS = [
    "AGUAS","CAMPAMENTO","CASILLAS","COOPERATIVA","ELCANO",
    "POLIGONO","PRADO","RAIMON","SINARCAS","POLIGONO2",
]


# ─── Definición de clientes nuevos/actualizados ───────────────────────────────

NUEVOS_CLIENTES = [

    # ── SANPEDRO ──────────────────────────────────────────────────────────────
    ClientCreate(
        code="SANPEDRO", name="Distribuidora San Pedro",
        notes="FTP en 78.47.127.86. 3 directorios: uploadPRIME, 202607, error. Error solo S14A y S29.",
        ftp_host="78.47.127.86", ftp_port=21, ftp_protocol="FTP",
        ftp_user="sanpedro", ftp_password="sanpedro",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Sanpedro/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/uploadPRIME", sort_order=0, active=True,
                notes="Directorio principal", file_patterns=patrones_std_3d()),
            DownloadRuleCreate(ftp_directory="/202607", sort_order=1, active=True,
                notes="Directorio mensual 202607", file_patterns=patrones_std_3d()),
            DownloadRuleCreate(ftp_directory="/error", sort_order=2, active=True,
                notes="Errores — solo S14A y S29",
                file_patterns=[
                    pat("*_S14A_*","S14A","S14A",3,1,0),
                    pat("*_S29_*","S29","S29",3,1,1),
                ]),
        ],
    ),

    # ── MOLARES ───────────────────────────────────────────────────────────────
    ClientCreate(
        code="MOLARES", name="Distribuidora Molares",
        notes="FTP en 213.98.131.59. 3 directorios: upload, error, 202607.",
        ftp_host="213.98.131.59", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0243", ftp_password="PkMn.6547",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Molares/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio principal", file_patterns=patrones_std_3d()),
            DownloadRuleCreate(ftp_directory="/error", sort_order=1, active=True,
                notes="Directorio error", file_patterns=patrones_std_3d()),
            DownloadRuleCreate(ftp_directory="/202607", sort_order=2, active=True,
                notes="Directorio mensual 202607", file_patterns=patrones_std_3d()),
        ],
    ),

    # ── MERCEDES ──────────────────────────────────────────────────────────────
    ClientCreate(
        code="MERCEDES", name="Las Mercedes",
        notes="FTP VPN. IP interna 192.168.127.151. Tamaños mínimos especiales. 2 directorios.",
        ftp_host="192.168.127.151", ftp_port=21, ftp_protocol="FTP",
        ftp_user="lasmercedes", ftp_password="Mercedes24$",
        ftp_timeout=45, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Mercedes/Import",
        vpn_required=True, vpn_config_file="mercedes.ovpn",
        schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=600,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio principal", file_patterns=patrones_mercedes()),
            DownloadRuleCreate(ftp_directory="/202607", sort_order=1, active=True,
                notes="Directorio mensual 202607", file_patterns=patrones_mercedes()),
        ],
    ),

    # ── MERCEDES_SABT ─────────────────────────────────────────────────────────
    # 7 conexiones FTP distintas al mismo servidor, cada una descarga desde raíz a SABT
    # Se modela como un cliente por cada usuario FTP (cada uno es un punto de suministro)
    # Agrupados bajo el mismo cliente con 7 reglas - pero al ser usuarios distintos
    # necesitan conexiones distintas → se modelan como clientes separados
    ClientCreate(
        code="MERCEDES_SABT_FRONTON", name="Mercedes SABT - Fronton",
        notes="VPN. FTP 192.168.127.151 usuario FRONTON. Descarga SABT desde raíz.",
        ftp_host="192.168.127.151", ftp_port=21, ftp_protocol="FTP",
        ftp_user="FRONTON", ftp_password="fronton",
        ftp_timeout=45, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Mercedes/Import",
        vpn_required=True, vpn_config_file="mercedes.ovpn",
        schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=600,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/", sort_order=0, active=True,
                notes="Raíz — todos los ficheros a SABT", file_patterns=patron_sabt(3)),
        ],
    ),
    ClientCreate(
        code="MERCEDES_SABT_TALLERES", name="Mercedes SABT - Talleres",
        notes="VPN. FTP 192.168.127.151 usuario TALLERES. Descarga SABT desde raíz.",
        ftp_host="192.168.127.151", ftp_port=21, ftp_protocol="FTP",
        ftp_user="TALLERES", ftp_password="talleres",
        ftp_timeout=45, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Mercedes/Import",
        vpn_required=True, vpn_config_file="mercedes.ovpn",
        schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=600,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/", sort_order=0, active=True,
                notes="Raíz — todos los ficheros a SABT", file_patterns=patron_sabt(3)),
        ],
    ),
    ClientCreate(
        code="MERCEDES_SABT_AMARGURA", name="Mercedes SABT - Amargura",
        notes="VPN. FTP 192.168.127.151 usuario AMARGURA. Descarga SABT desde raíz.",
        ftp_host="192.168.127.151", ftp_port=21, ftp_protocol="FTP",
        ftp_user="AMARGURA", ftp_password="amargura",
        ftp_timeout=45, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Mercedes/Import",
        vpn_required=True, vpn_config_file="mercedes.ovpn",
        schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=600,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/", sort_order=0, active=True,
                notes="Raíz — todos los ficheros a SABT", file_patterns=patron_sabt(3)),
        ],
    ),
    ClientCreate(
        code="MERCEDES_SABT_REMEDIOS", name="Mercedes SABT - Remedios",
        notes="VPN. FTP 192.168.127.151 usuario REMEDIOS. Descarga SABT desde raíz.",
        ftp_host="192.168.127.151", ftp_port=21, ftp_protocol="FTP",
        ftp_user="REMEDIOS", ftp_password="remedios",
        ftp_timeout=45, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Mercedes/Import",
        vpn_required=True, vpn_config_file="mercedes.ovpn",
        schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=600,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/", sort_order=0, active=True,
                notes="Raíz — todos los ficheros a SABT", file_patterns=patron_sabt(3)),
        ],
    ),
    ClientCreate(
        code="MERCEDES_SABT_SOLANA", name="Mercedes SABT - Solana",
        notes="VPN. FTP 192.168.127.151 usuario SOLANA. Antigüedad 30D.",
        ftp_host="192.168.127.151", ftp_port=21, ftp_protocol="FTP",
        ftp_user="SOLANA", ftp_password="solana",
        ftp_timeout=45, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Mercedes/Import",
        vpn_required=True, vpn_config_file="mercedes.ovpn",
        schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=600,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/", sort_order=0, active=True,
                notes="Raíz — ficheros a SABT con antigüedad 30D",
                file_patterns=[pat("*_*","SABT","SABT",30,1,0)]),
        ],
    ),
    ClientCreate(
        code="MERCEDES_SABT_EDUARDO", name="Mercedes SABT - Eduardo",
        notes="VPN. FTP 192.168.127.151 usuario EDUARDO. Descarga SABT desde raíz.",
        ftp_host="192.168.127.151", ftp_port=21, ftp_protocol="FTP",
        ftp_user="EDUARDO", ftp_password="eduardo",
        ftp_timeout=45, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Mercedes/Import",
        vpn_required=True, vpn_config_file="mercedes.ovpn",
        schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=600,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/", sort_order=0, active=True,
                notes="Raíz — todos los ficheros a SABT", file_patterns=patron_sabt(3)),
        ],
    ),
    ClientCreate(
        code="MERCEDES_SABT_GUISANDERAS", name="Mercedes SABT - Guisanderas",
        notes="VPN. FTP 192.168.127.151 usuario GUISANDERAS. Descarga SABT desde raíz.",
        ftp_host="192.168.127.151", ftp_port=21, ftp_protocol="FTP",
        ftp_user="GUISANDERAS", ftp_password="guisanderas",
        ftp_timeout=45, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Mercedes/Import",
        vpn_required=True, vpn_config_file="mercedes.ovpn",
        schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=600,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/", sort_order=0, active=True,
                notes="Raíz — todos los ficheros a SABT", file_patterns=patron_sabt(3)),
        ],
    ),

    # ── LAPROHIDA ─────────────────────────────────────────────────────────────
    ClientCreate(
        code="LAPROHIDA", name="La Prohida",
        notes="FTP puerto 42121 en 109.234.71.91. Tamaños mínimos especiales. 2 directorios.",
        ftp_host="109.234.71.91", ftp_port=42121, ftp_protocol="FTP",
        ftp_user="prohida", ftp_password="pro132ftp637hida",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Laprohida/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio principal", file_patterns=patrones_laprohida()),
            DownloadRuleCreate(ftp_directory="/202607", sort_order=1, active=True,
                notes="Directorio mensual 202607", file_patterns=patrones_laprohida()),
        ],
    ),

    # ── ALVAROBENITO ──────────────────────────────────────────────────────────
    ClientCreate(
        code="ALVAROBENITO", name="Álvaro Benito",
        notes="FTP puerto 42121 en 109.234.71.91. 3 directorios: upload, 202607, error.",
        ftp_host="109.234.71.91", ftp_port=42121, ftp_protocol="FTP",
        ftp_user="abenito", ftp_password="benito321ftp",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Alvarobenito/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio principal", file_patterns=patrones_std_3d()),
            DownloadRuleCreate(ftp_directory="/202607", sort_order=1, active=True,
                notes="Directorio mensual 202607", file_patterns=patrones_std_3d()),
            DownloadRuleCreate(ftp_directory="/error", sort_order=2, active=True,
                notes="Errores — solo S26",
                file_patterns=[pat("*_S26_*","S26","S26",1,1,0)]),
        ],
    ),

    # ── HELIODORO ─────────────────────────────────────────────────────────────
    ClientCreate(
        code="HELIODORO", name="Heliodoro",
        notes="FTP 82.159.192.202. Patrones con prefijo CIR4621748247. Directorio /upload.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0413", ftp_password="bOoM.5568",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Heliodoro/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio principal — patrones con prefijo CIR4621748247",
                file_patterns=patrones_heliodoro()),
        ],
    ),

    # ── HELIODORO_SABT ────────────────────────────────────────────────────────
    ClientCreate(
        code="HELIODORO_SABT", name="Heliodoro SABT",
        notes="FTP 82.159.192.202 mismo usuario que Heliodoro. Directorio SABT. Transferencia ASCII.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0413", ftp_password="bOoM.5568",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Heliodoro/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/SABT", sort_order=0, active=True,
                notes="Directorio SABT — patrón comodín",
                file_patterns=patron_sabt(3)),
        ],
    ),

    # ── ACSI ──────────────────────────────────────────────────────────────────
    # Tiene 2 conexiones FTP distintas (2 servidores distintos) → 2 clientes
    ClientCreate(
        code="ACSI_MEDIDAS", name="ACSI - Medidas",
        notes="FTP 80.59.212.213 usuario outumuro. Directorio /Medidas. Timeout 300s.",
        ftp_host="80.59.212.213", ftp_port=21, ftp_protocol="FTP",
        ftp_user="outumuro", ftp_password="=42e51QoF3%U",
        ftp_timeout=300, ftp_passive=True,
        local_base_path="C:/FTP/Acsi",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/Medidas", sort_order=0, active=True,
                notes="Directorio Medidas", file_patterns=patrones_std_3d()),
        ],
    ),
    ClientCreate(
        code="ACSI_UPLOAD", name="ACSI - Upload",
        notes="FTP 80.59.212.213 usuario telegestion. Directorio /upload.",
        ftp_host="80.59.212.213", ftp_port=21, ftp_protocol="FTP",
        ftp_user="telegestion", ftp_password="mus123",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/FTP/Acsi",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio upload", file_patterns=patrones_std_3d()),
        ],
    ),

    # ── SANTACLARA_SABT ───────────────────────────────────────────────────────
    ClientCreate(
        code="SANTACLARA_SABT", name="Santa Clara SABT",
        notes="VPN. FTP 192.168.127.150 mismo usuario que Santaclara. 6 directorios SABT.",
        ftp_host="192.168.127.150", ftp_port=21, ftp_protocol="FTP",
        ftp_user="celnet", ftp_password="Cn1720$%",
        ftp_timeout=45, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Santaclara/Import",
        vpn_required=True, vpn_config_file="santaclara.ovpn",
        schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=600,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/POCITO", sort_order=0, active=True,
                notes="SABT Pocito", file_patterns=patron_sabt(3)),
            DownloadRuleCreate(ftp_directory="/GUADALCANAL", sort_order=1, active=True,
                notes="SABT Guadalcanal", file_patterns=patron_sabt(3)),
            DownloadRuleCreate(ftp_directory="/GALLOS", sort_order=2, active=True,
                notes="SABT Gallos", file_patterns=patron_sabt(3)),
            DownloadRuleCreate(ftp_directory="/PILAR", sort_order=3, active=True,
                notes="SABT Pilar", file_patterns=patron_sabt(3)),
            DownloadRuleCreate(ftp_directory="/EGB", sort_order=4, active=True,
                notes="SABT EGB", file_patterns=patron_sabt(3)),
            DownloadRuleCreate(ftp_directory="/COOPERATIVA", sort_order=5, active=True,
                notes="SABT Cooperativa", file_patterns=patron_sabt(3)),
        ],
    ),

    # ── PASTOR_SABT ───────────────────────────────────────────────────────────
    ClientCreate(
        code="PASTOR_SABT", name="Pastor SABT",
        notes="FTP 82.159.192.202 usuario ftp_0267. Directorio SABT. Transferencia ASCII.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0267", ftp_password="aXmM.2473",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Pastor/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/SABT", sort_order=0, active=True,
                notes="Directorio SABT", file_patterns=patron_sabt(3)),
        ],
    ),

    # ── LEANDRO ───────────────────────────────────────────────────────────────
    ClientCreate(
        code="LEANDRO", name="Leandro",
        notes="FTP 82.159.192.202. Patrones con antigüedad 2D. Sin S24.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0335", ftp_password="aTMe.6520",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Leandro/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio único — antigüedad 2D, sin S24",
                file_patterns=[
                    pat("*_S04_*","S04","S04",2,1,0), pat("*_S05_*","S05","S05",2,1,1),
                    pat("*_S02_*","S02","S02",2,1,2), pat("*_S09_*","S09","S09",2,1,3),
                    pat("*_G01_*","G01","G01",2,1,4), pat("*_G02_*","G02","G02",2,1,5),
                    pat("*_S06_*","S06","S06",2,1,6), pat("*_S12_*","S12","S12",2,1,7),
                    pat("*_S14_*","S14","S14",2,1,8), pat("*_S17_*","S17","S17",2,1,9),
                    pat("*_S23_*","S23","S23",2,1,10), pat("*_S26_*","S26","S26",1,1,11),
                ]),
        ],
    ),

    # ── ALBORENSE ─────────────────────────────────────────────────────────────
    ClientCreate(
        code="ALBORENSE", name="Alborense",
        notes="FTP 82.159.192.202. Patrones con antigüedad 2D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0136", ftp_password="CoEa.8776",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Alborense/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio único — antigüedad 2D",
                file_patterns=patrones_std_2d()),
        ],
    ),

    # ── CERRAJON ──────────────────────────────────────────────────────────────
    ClientCreate(
        code="CERRAJON", name="Cerrajón",
        notes="FTP 82.159.192.202. Patrones estándar 3D.",
        ftp_host="82.159.192.202", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftp_0307", ftp_password="bnGF.2507",
        ftp_timeout=30, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Cerrajon/Import",
        vpn_required=False, schedule_cron="0 6 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            DownloadRuleCreate(ftp_directory="/upload", sort_order=0, active=True,
                notes="Directorio único", file_patterns=patrones_std_3d()),
        ],
    ),

    # ── TALAYUELAS ────────────────────────────────────────────────────────────
    ClientCreate(
        code="TALAYUELAS", name="Talayuelas",
        notes="FTP 185.31.238.178 mismas credenciales que Coelca. 10 almacenes bajo /329/ x 6 subdirectorios.",
        ftp_host="185.31.238.178", ftp_port=21, ftp_protocol="FTP",
        ftp_user="ftpalgi", ftp_password="PfL1DmeeP",
        ftp_timeout=60, ftp_passive=True,
        local_base_path="C:/GD/Distribuidoras/Talayuelas/Import",
        vpn_required=False, schedule_cron="30 5 * * 1-6",
        schedule_active=True, retry_attempts=3, retry_delay_seconds=300,
        download_rules=[
            rule
            for i, almacen in enumerate(ALMACENES_TALAYUELAS)
            for rule in reglas_coelca_style("329", almacen, i * 6)
        ],
    ),
]

# ─── Clientes a actualizar ────────────────────────────────────────────────────

ACTUALIZACIONES = {
    # VARGAS: nuevas credenciales, nuevo host, 19 almacenes
    "VARGAS": {
        "update": {
            "ftp_host": "cc2.infocononline.com",
            "ftp_port": 21,
            "ftp_user": "va_cuartel",
            "ftp_password": "R45*L3CT4A8w",
            "notes": "FTP en cc2.infocononline.com. 19 almacenes bajo /Vargas/VA_*/Upload.",
        },
        "replace_rules": [
            DownloadRuleCreate(
                ftp_directory=f"/Vargas/{almacen}/Upload",
                sort_order=i, active=True,
                notes=f"Almacén {almacen}",
                file_patterns=patrones_std_3d(),
            )
            for i, almacen in enumerate(ALMACENES_VARGAS)
        ],
    },
    # SANTACLARA: actualizar directorio mensual de 202606 a 202607
    "SANTACLARA": {
        "update": {"notes": "Requiere VPN. IP interna 192.168.127.150. 3 directorios."},
        "update_rule_notes": {"/202606": {"ftp_directory": "/202607", "notes": "Directorio mensual 202607"}},
    },
}


# ─── Runner ───────────────────────────────────────────────────────────────────

async def seed():
    print("=" * 60)
    print("SEED BATCH 2 — Nuevos clientes y actualizaciones")
    print("=" * 60)

    async with AsyncSessionLocal() as db:

        # ── Actualizaciones ──────────────────────────────────────────────────
        print("\n📝 Actualizando clientes existentes...")
        for code, cambios in ACTUALIZACIONES.items():
            client = await ClientService.get_by_code(db, code)
            if not client:
                print(f"  ⚠️  {code} no encontrado, omitiendo actualización")
                continue

            # Actualizar campos básicos
            if "update" in cambios:
                update_data = cambios["update"]
                for field, value in update_data.items():
                    setattr(client, field, value)
                print(f"  ✓  {code} — campos actualizados")

            # Reemplazar reglas completas
            if "replace_rules" in cambios:
                await db.execute(delete(DownloadRule).where(DownloadRule.client_id == client.id))
                await db.flush()
                for rule_data in cambios["replace_rules"]:
                    from app.services.client_service import ClientService as CS
                    rule_dict = rule_data.model_dump()
                    # Convertir file_patterns de objetos Pydantic a dicts
                    rule_dict["file_patterns"] = [
                        p.model_dump() if hasattr(p, "model_dump") else p
                        for p in rule_dict.get("file_patterns", [])
                    ]
                    await CS.add_rule(db, client.id, rule_dict)
                print(f"  ✓  {code} — {len(cambios['replace_rules'])} reglas reemplazadas")

                
            # Actualizar reglas específicas por directorio
            if "update_rule_notes" in cambios:
                from sqlalchemy.orm import selectinload
                from sqlalchemy import select as sa_select
                from app.models.models import DownloadRule as DR
                for old_dir, new_data in cambios["update_rule_notes"].items():
                    q = sa_select(DR).where(
                        DR.client_id == client.id,
                        DR.ftp_directory == old_dir
                    )
                    result = await db.execute(q)
                    rule = result.scalar_one_or_none()
                    if rule:
                        for field, value in new_data.items():
                            setattr(rule, field, value)
                        print(f"  ✓  {code} — regla {old_dir} → {new_data.get('ftp_directory', old_dir)}")
                    else:
                        print(f"  ⚠️  {code} — regla {old_dir} no encontrada")

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
    print("Seed completado.")
    print("\nResumen de clientes nuevos:")
    for c in NUEVOS_CLIENTES:
        vpn = " [VPN]" if c.vpn_required else ""
        print(f"  {c.code:30} {c.ftp_host:25} {len(c.download_rules):3} reglas{vpn}")


if __name__ == "__main__":
    asyncio.run(seed())