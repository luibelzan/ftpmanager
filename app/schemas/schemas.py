from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from app.models.models import FtpProtocol, AlertLevel, AlertType, JobStatus


# ─── File Pattern ─────────────────────────────────────────────────────────────

class FilePatternBase(BaseModel):
    pattern: str = Field(..., example="*_S04_*")
    file_type: str = Field(..., example="S04")
    local_subfolder: str = Field(..., example="S04")
    min_age_days: int = Field(1, ge=0)
    min_size_bytes: int = Field(1, ge=0)
    sort_order: int = 0


class FilePatternCreate(FilePatternBase):
    pass


class FilePatternOut(FilePatternBase):
    id: str
    rule_id: str

    model_config = {"from_attributes": True}


# ─── Download Rule ────────────────────────────────────────────────────────────

class DownloadRuleBase(BaseModel):
    ftp_directory: str = Field(..., example="/upload")
    sort_order: int = 0
    active: bool = True
    notes: Optional[str] = None


class DownloadRuleCreate(DownloadRuleBase):
    file_patterns: list[FilePatternCreate] = []


class DownloadRuleOut(DownloadRuleBase):
    id: str
    client_id: str
    file_patterns: list[FilePatternOut] = []

    model_config = {"from_attributes": True}


# ─── Client ───────────────────────────────────────────────────────────────────

class ClientBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=50, example="FEREZ")
    name: str = Field(..., example="Distribuidora Ferez S.L.")
    notes: Optional[str] = None

    # FTP
    ftp_host: str = Field(..., example="82.159.192.202")
    ftp_port: int = Field(21, ge=1, le=65535)
    ftp_protocol: FtpProtocol = FtpProtocol.FTP
    ftp_user: str
    ftp_password: str
    ftp_timeout: int = Field(30, ge=5, le=300)
    ftp_passive: bool = True

    # Ruta local
    local_base_path: str = Field(..., example="C:/GD/Distribuidoras/Ferez/Import")

    # VPN
    vpn_required: bool = False
    vpn_config_file: Optional[str] = None

    # Scheduler
    schedule_cron: Optional[str] = Field(None, example="0 6 * * 1-5")
    schedule_active: bool = True
    retry_attempts: int = Field(3, ge=0, le=10)
    retry_delay_seconds: int = Field(300, ge=30)

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("vpn_config_file")
    @classmethod
    def check_vpn_config(cls, v, info):
        if info.data.get("vpn_required") and not v:
            raise ValueError("Se requiere vpn_config_file cuando vpn_required es True")
        return v


class ClientCreate(ClientBase):
    download_rules: list[DownloadRuleCreate] = []
    active: bool = True


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None
    ftp_host: Optional[str] = None
    ftp_port: Optional[int] = None
    ftp_protocol: Optional[FtpProtocol] = None
    ftp_user: Optional[str] = None
    ftp_password: Optional[str] = None
    ftp_timeout: Optional[int] = None
    ftp_passive: Optional[bool] = None
    local_base_path: Optional[str] = None
    vpn_required: Optional[bool] = None
    vpn_config_file: Optional[str] = None
    schedule_cron: Optional[str] = None
    schedule_active: Optional[bool] = None
    retry_attempts: Optional[int] = None
    retry_delay_seconds: Optional[int] = None
    active: Optional[bool] = None


class ClientOut(ClientBase):
    id: str
    active: bool
    created_at: datetime
    updated_at: datetime
    download_rules: list[DownloadRuleOut] = []
    ftp_password: str = Field(exclude=True)

    model_config = {"from_attributes": True}


class ClientSummary(BaseModel):
    id: str
    code: str
    name: str
    active: bool
    ftp_host: str
    ftp_protocol: FtpProtocol
    vpn_required: bool
    schedule_cron: Optional[str]
    schedule_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Job Execution ────────────────────────────────────────────────────────────

class JobExecutionOut(BaseModel):
    id: str
    client_id: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: JobStatus
    files_downloaded: int
    files_by_type: Optional[dict]
    error_message: Optional[str]
    duration_seconds: Optional[float]
    vpn_used: bool
    triggered_by: str

    model_config = {"from_attributes": True}


# ─── Alert ────────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: str
    client_id: Optional[str]
    created_at: datetime
    level: AlertLevel
    alert_type: AlertType
    message: str
    acknowledged: bool
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    notified_telegram: bool
    job_execution_id: Optional[str]

    model_config = {"from_attributes": True}


class AlertAck(BaseModel):
    acknowledged_by: str = Field(..., example="admin")


# ─── Dashboard ────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    files_today: int
    files_week: int
    active_clients: int
    total_clients: int
    clients_with_errors: int
    pending_alerts: int
    files_by_type_today: dict[str, int]
    last_executions: list[JobExecutionOut]
    recent_alerts: list[AlertOut]


# ─── FTP Test ─────────────────────────────────────────────────────────────────

class FtpTestRequest(BaseModel):
    ftp_host: str
    ftp_port: int = 21
    ftp_protocol: FtpProtocol = FtpProtocol.FTP
    ftp_user: str
    ftp_password: str
    ftp_timeout: int = 15
    ftp_passive: bool = True


class FtpTestResult(BaseModel):
    success: bool
    message: str
    duration_ms: Optional[float] = None
    directories: list[str] = []