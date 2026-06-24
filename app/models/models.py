import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, Boolean, DateTime, Text, Float,
    ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class FtpProtocol(str, enum.Enum):
    FTP = "FTP"
    FTPS = "FTPS"
    SFTP = "SFTP"


class AlertLevel(str, enum.Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class AlertType(str, enum.Enum):
    VPN_DOWN = "VPN_DOWN"
    FTP_CONNECTION_ERROR = "FTP_CONNECTION_ERROR"
    FTP_NO_FILES = "FTP_NO_FILES"
    DOWNLOAD_ERROR = "DOWNLOAD_ERROR"
    TASK_NOT_RUN = "TASK_NOT_RUN"
    DISK_WRITE_ERROR = "DISK_WRITE_ERROR"


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


# ─── Client ──────────────────────────────────────────────────────────────────

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Conexión FTP
    ftp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    ftp_port: Mapped[int] = mapped_column(Integer, default=21)
    ftp_protocol: Mapped[FtpProtocol] = mapped_column(SAEnum(FtpProtocol), default=FtpProtocol.FTP)
    ftp_user: Mapped[str] = mapped_column(String(100), nullable=False)
    ftp_password: Mapped[str] = mapped_column(String(255), nullable=False)
    ftp_timeout: Mapped[int] = mapped_column(Integer, default=30)
    ftp_passive: Mapped[bool] = mapped_column(Boolean, default=True)

    # Carpeta base de descarga local
    local_base_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # VPN
    vpn_required: Mapped[bool] = mapped_column(Boolean, default=False)
    vpn_config_file: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Scheduler (expresión cron)
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    schedule_active: Mapped[bool] = mapped_column(Boolean, default=True)
    retry_attempts: Mapped[int] = mapped_column(Integer, default=3)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, default=300)

    # Relaciones
    download_rules: Mapped[list["DownloadRule"]] = relationship(
        "DownloadRule", back_populates="client", cascade="all, delete-orphan",
        order_by="DownloadRule.sort_order"
    )
    job_executions: Mapped[list["JobExecution"]] = relationship(
        "JobExecution", back_populates="client", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="client", cascade="all, delete-orphan"
    )


# ─── Download Rule ────────────────────────────────────────────────────────────

class DownloadRule(Base):
    __tablename__ = "download_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    ftp_directory: Mapped[str] = mapped_column(String(500), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    client: Mapped["Client"] = relationship("Client", back_populates="download_rules")
    file_patterns: Mapped[list["FilePattern"]] = relationship(
        "FilePattern", back_populates="rule", cascade="all, delete-orphan",
        order_by="FilePattern.sort_order"
    )


# ─── File Pattern ─────────────────────────────────────────────────────────────

class FilePattern(Base):
    __tablename__ = "file_patterns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("download_rules.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    pattern: Mapped[str] = mapped_column(String(200), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    local_subfolder: Mapped[str] = mapped_column(String(200), nullable=False)
    min_age_days: Mapped[int] = mapped_column(Integer, default=1)
    min_size_bytes: Mapped[int] = mapped_column(Integer, default=1)

    rule: Mapped["DownloadRule"] = relationship("DownloadRule", back_populates="file_patterns")


# ─── Job Execution ────────────────────────────────────────────────────────────

class JobExecution(Base):
    __tablename__ = "job_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus), default=JobStatus.PENDING)
    files_downloaded: Mapped[int] = mapped_column(Integer, default=0)
    files_by_type: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    vpn_used: Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_by: Mapped[str] = mapped_column(String(50), default="scheduler")

    client: Mapped["Client"] = relationship("Client", back_populates="job_executions")


# ─── Alert ────────────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    client_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clients.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    level: Mapped[AlertLevel] = mapped_column(SAEnum(AlertLevel), nullable=False)
    alert_type: Mapped[AlertType] = mapped_column(SAEnum(AlertType), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notified_telegram: Mapped[bool] = mapped_column(Boolean, default=False)
    job_execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    client: Mapped["Client | None"] = relationship("Client", back_populates="alerts")