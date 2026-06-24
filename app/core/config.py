from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base de datos
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    # Seguridad
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Rutas
    BASE_DOWNLOAD_PATH: str = "C:/GD/Distribuidoras"
    LOG_DIR: str = "C:/GD/logs/ftpmanager"

    # OpenVPN
    OPENVPN_BIN: str = "openvpn"
    OPENVPN_CONFIG_DIR: str = "C:/GD/config/vpn"

    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # Entorno
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    @field_validator("BASE_DOWNLOAD_PATH", "LOG_DIR", mode="after")
    @classmethod
    def create_dirs(cls, v: str) -> str:
        os.makedirs(v, exist_ok=True)
        return v


settings = Settings()