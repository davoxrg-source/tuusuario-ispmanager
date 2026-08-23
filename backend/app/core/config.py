from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://ispmanager:changeme@localhost:5432/ispmanager"

    secret_key: str = "changeme"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    credentials_encryption_key: str = ""

    device_poll_interval_seconds: int = 300

    # Colector NetFlow v5 (ver services/netflow/collector.py) para uso de
    # tráfico por cliente. netflow_public_host es la IP/host de este backend
    # que se le indica a cada Mikrotik como target de /ip/traffic-flow -- si
    # queda vacío, el poller no intenta auto-configurar ningún equipo.
    netflow_collector_port: int = 2055
    netflow_public_host: str = ""
    netflow_retention_days: int = 90

    environment: str = "production"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
