import ftplib
import paramiko
import fnmatch
import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field

from app.models.models import Client, DownloadRule, FilePattern, FtpProtocol

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    success: bool
    files_downloaded: int = 0
    files_by_type: dict = field(default_factory=dict)
    error_message: Optional[str] = None
    duration_seconds: float = 0.0


class FtpEngine:

    def __init__(self, client: Client):
        self.client = client
        self._ftp: Optional[ftplib.FTP] = None
        self._sftp: Optional[paramiko.SFTPClient] = None
        self._ssh: Optional[paramiko.SSHClient] = None

    # ─── Conexión ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        protocol = self.client.ftp_protocol
        host = self.client.ftp_host
        port = self.client.ftp_port
        user = self.client.ftp_user
        password = self.client.ftp_password
        timeout = self.client.ftp_timeout

        logger.info(f"[{self.client.code}] Conectando {protocol} a {host}:{port}")

        if protocol == FtpProtocol.SFTP:
            self._connect_sftp(host, port, user, password, timeout)
        elif protocol == FtpProtocol.FTPS:
            self._connect_ftps(host, port, user, password, timeout)
        else:
            self._connect_ftp(host, port, user, password, timeout)

    def _connect_ftp(self, host, port, user, password, timeout):
        self._ftp = ftplib.FTP(timeout=timeout)
        self._ftp.connect(host, port)
        self._ftp.login(user, password)
        if self.client.ftp_passive:
            self._ftp.set_pasv(True)
        logger.info(f"[{self.client.code}] FTP conectado OK")

    def _connect_ftps(self, host, port, user, password, timeout):
        self._ftp = ftplib.FTP_TLS(timeout=timeout)
        self._ftp.connect(host, port)
        self._ftp.login(user, password)
        self._ftp.prot_p()
        if self.client.ftp_passive:
            self._ftp.set_pasv(True)
        logger.info(f"[{self.client.code}] FTPS conectado OK")

    def _connect_sftp(self, host, port, user, password, timeout):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(host, port=port, username=user, password=password, timeout=timeout)
        self._sftp = self._ssh.open_sftp()
        logger.info(f"[{self.client.code}] SFTP conectado OK")

    def disconnect(self):
        try:
            if self._ftp:
                self._ftp.quit()
        except Exception:
            pass
        try:
            if self._sftp:
                self._sftp.close()
            if self._ssh:
                self._ssh.close()
        except Exception:
            pass

    # ─── Listado remoto ───────────────────────────────────────────────────────

    def list_directory(self, remote_path: str) -> list[dict]:
        if self._sftp:
            return self._list_sftp(remote_path)
        return self._list_ftp(remote_path)

    def _list_ftp(self, remote_path: str) -> list[dict]:
        self._ftp.cwd(remote_path)
        files = []

        # Intentar MLSD primero
        try:
            entries = []
            self._ftp.retrlines("MLSD", entries.append)
            logger.info(f"[{self.client.code}] Usando MLSD en {remote_path}")
            for entry in entries:
                parts = entry.split(";")
                facts = {}
                for p in parts[:-1]:
                    if "=" in p:
                        k, v = p.strip().split("=", 1)
                        facts[k.lower()] = v
                name = parts[-1].strip()
                if facts.get("type", "").lower() == "file":
                    size = int(facts.get("size", 0))
                    mtime_str = facts.get("modify", "")
                    try:
                        mtime = datetime.strptime(mtime_str[:14], "%Y%m%d%H%M%S")
                    except Exception:
                        mtime = datetime.utcnow()
                    files.append({"name": name, "size": size, "mtime": mtime})

        except Exception as e:
            # Fallback a LIST
            logger.info(f"[{self.client.code}] MLSD no soportado en {remote_path} ({e}), usando LIST con MDTM")
            raw_lines = []
            self._ftp.retrlines("LIST", raw_lines.append)
            for line in raw_lines:
                parts = line.split()
                if len(parts) < 9:
                    continue
                perms = parts[0]
                if perms.startswith("d"):
                    continue
                try:
                    size = int(parts[4])
                except ValueError:
                    size = 0
                name = " ".join(parts[8:])

                # Intentar obtener fecha real con MDTM
                try:
                    mdtm_resp = self._ftp.sendcmd(f"MDTM {name}")
                    mdtm_str = mdtm_resp.split()[-1]
                    mtime = datetime.strptime(mdtm_str[:14], "%Y%m%d%H%M%S")
                    logger.debug(f"[{self.client.code}] MDTM OK: {name} → {mtime}")
                except Exception:
                    # Si MDTM tampoco funciona, usar fecha aproximada
                    logger.warning(f"[{self.client.code}] MDTM no disponible para {name}, usando fecha aproximada")
                    mtime = datetime.utcnow() - timedelta(days=2)

                files.append({"name": name, "size": size, "mtime": mtime})

        return files

    def _list_sftp(self, remote_path: str) -> list[dict]:
        files = []
        for attr in self._sftp.listdir_attr(remote_path):
            if not attr.st_mode or (attr.st_mode & 0o040000):
                continue
            mtime = datetime.utcfromtimestamp(attr.st_mtime) if attr.st_mtime else datetime.utcnow()
            files.append({"name": attr.filename, "size": attr.st_size or 0, "mtime": mtime})
        return files

    # ─── Descarga ─────────────────────────────────────────────────────────────

    def download_file(self, remote_path: str, local_path: str) -> None:
        if self._sftp:
            self._sftp.get(remote_path, local_path)
        else:
            with open(local_path, "wb") as f:
                self._ftp.retrbinary(f"RETR {remote_path}", f.write)

    # ─── Lógica principal ─────────────────────────────────────────────────────

    def execute_rules(self) -> DownloadResult:
        start = datetime.utcnow()
        total_files = 0
        files_by_type: dict[str, int] = {}

        try:
            self.connect()

            for rule in self.client.download_rules:
                if not rule.active:
                    continue
                rule_count, rule_by_type = self._execute_rule(rule)
                total_files += rule_count
                for ftype, cnt in rule_by_type.items():
                    files_by_type[ftype] = files_by_type.get(ftype, 0) + cnt

        except Exception as exc:
            logger.error(f"[{self.client.code}] Error fatal: {exc}")
            duration = (datetime.utcnow() - start).total_seconds()
            return DownloadResult(
                success=False,
                files_downloaded=total_files,
                files_by_type=files_by_type,
                error_message=str(exc),
                duration_seconds=round(duration, 2),
            )
        finally:
            self.disconnect()

        duration = (datetime.utcnow() - start).total_seconds()
        logger.info(f"[{self.client.code}] Completado: {total_files} ficheros en {duration:.1f}s")
        return DownloadResult(
            success=True,
            files_downloaded=total_files,
            files_by_type=files_by_type,
            duration_seconds=round(duration, 2),
        )

    def _execute_rule(self, rule: DownloadRule) -> tuple[int, dict]:
        logger.info(f"[{self.client.code}] cd {rule.ftp_directory}")
        count = 0
        by_type: dict[str, int] = {}

        try:
            remote_files = self.list_directory(rule.ftp_directory)
        except Exception as exc:
            logger.warning(f"[{self.client.code}] No se pudo listar {rule.ftp_directory}: {exc}")
            return 0, {}

        for pattern in rule.file_patterns:
            matched = self._match_files(remote_files, pattern)
            for f in matched:
                dest_dir = os.path.join(self.client.local_base_path, pattern.local_subfolder)
                os.makedirs(dest_dir, exist_ok=True)
                local_path = os.path.join(dest_dir, f["name"])

                if os.path.exists(local_path) and os.path.getsize(local_path) == f["size"]:
                    logger.debug(f"[{self.client.code}] Ya existe: {f['name']}")
                    continue

                remote_full = f"{rule.ftp_directory.rstrip('/')}/{f['name']}"
                try:
                    self.download_file(remote_full, local_path)
                    count += 1
                    by_type[pattern.file_type] = by_type.get(pattern.file_type, 0) + 1
                    logger.info(f"[{self.client.code}] ✓ {f['name']} → {pattern.local_subfolder}/")
                except Exception as exc:
                    logger.error(f"[{self.client.code}] Error descargando {f['name']}: {exc}")

        return count, by_type

    def _match_files(self, files: list[dict], pattern: FilePattern) -> list[dict]:
        now = datetime.utcnow()
        min_age_threshold = now - timedelta(days=pattern.min_age_days)
        result = []
        for f in files:
            name_ok = fnmatch.fnmatch(f["name"], pattern.pattern)
            age_ok = f["mtime"] >= min_age_threshold
            size_ok = f["size"] >= pattern.min_size_bytes
            if name_ok and age_ok and size_ok:
                result.append(f)
        return result

    # ─── Test de conexión ─────────────────────────────────────────────────────

    @staticmethod
    def test_connection(host: str, port: int, protocol: FtpProtocol,
                        user: str, password: str, timeout: int = 15,
                        passive: bool = True) -> dict:
        import time
        start = time.time()
        try:
            if protocol == FtpProtocol.SFTP:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(host, port=port, username=user, password=password, timeout=timeout)
                sftp = ssh.open_sftp()
                dirs = sftp.listdir(".")
                sftp.close()
                ssh.close()
            elif protocol == FtpProtocol.FTPS:
                ftp = ftplib.FTP_TLS(timeout=timeout)
                ftp.connect(host, port)
                ftp.login(user, password)
                ftp.prot_p()
                dirs = ftp.nlst()
                ftp.quit()
            else:
                ftp = ftplib.FTP(timeout=timeout)
                ftp.connect(host, port)
                ftp.login(user, password)
                ftp.set_pasv(passive)
                dirs = ftp.nlst()
                ftp.quit()

            ms = round((time.time() - start) * 1000, 1)
            return {"success": True, "message": "Conexión exitosa", "duration_ms": ms, "directories": dirs[:20]}
        except Exception as exc:
            ms = round((time.time() - start) * 1000, 1)
            return {"success": False, "message": str(exc), "duration_ms": ms, "directories": []}