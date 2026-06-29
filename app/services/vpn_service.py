import asyncio
import subprocess
import logging
import os
import socket
import time
from typing import Optional

from app.core.config import settings
from app.models.models import Client

logger = logging.getLogger(__name__)

# Proceso activo por cliente: {client_code: subprocess.Popen}
_active_tunnels: dict[str, subprocess.Popen] = {}


class VpnService:

    @staticmethod
    def config_path(config_file: str) -> str:
        if os.path.isabs(config_file):
            return config_file
        return os.path.join(settings.OPENVPN_CONFIG_DIR, config_file)

    @staticmethod
    async def connect(client: Client) -> bool:
        code = client.code
        if code in _active_tunnels:
            logger.info(f"[VPN:{code}] Túnel ya activo, reutilizando")
            return True

        config = os.path.normpath(VpnService.config_path(client.vpn_config_file))

        if not os.path.exists(config):
            raise FileNotFoundError(f"Fichero VPN no encontrado: {config}")

        openvpn_bin = os.path.normpath(settings.OPENVPN_BIN)
        log_file = os.path.join(settings.OPENVPN_CONFIG_DIR, f"vpn_{code}.log")

        cmd = [
            openvpn_bin,
            "--config", config,
            "--log", log_file,
            "--verb", "4",
        ]

        logger.info(f"[VPN:{code}] Iniciando túnel: {config}")
        logger.info(f"[VPN:{code}] Log OpenVPN en: {log_file}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(config),
        )
        _active_tunnels[code] = proc

        connected = await VpnService._wait_for_tunnel(client.ftp_host, client.ftp_port, timeout=60)

        if not connected:
            # Leer las últimas líneas del log para diagnóstico
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    last_lines = f.readlines()[-20:]
                logger.error(f"[VPN:{code}] Últimas líneas del log OpenVPN:")
                for line in last_lines:
                    logger.error(f"[VPN:{code}] {line.rstrip()}")
            except Exception:
                pass

            VpnService.disconnect(code)
            raise ConnectionError(f"[VPN:{code}] El túnel no llegó a establecerse en 60 s")

        logger.info(f"[VPN:{code}] Túnel activo")
        return True

    @staticmethod
    async def _wait_for_tunnel(host: str, port: int, timeout: int = 20) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                sock = socket.create_connection((host, port), timeout=2)
                sock.close()
                return True
            except (OSError, ConnectionRefusedError):
                await asyncio.sleep(2)
        return False

    @staticmethod
    def disconnect(code: str) -> None:
        proc = _active_tunnels.pop(code, None)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception as exc:
                logger.warning(f"[VPN:{code}] Error al cerrar túnel: {exc}")
            logger.info(f"[VPN:{code}] Túnel cerrado")

    @staticmethod
    def is_active(code: str) -> bool:
        proc = _active_tunnels.get(code)
        if not proc:
            return False
        return proc.poll() is None

    @staticmethod
    def status_all() -> dict[str, str]:
        return {
            code: ("activo" if proc.poll() is None else "caído")
            for code, proc in _active_tunnels.items()
        }