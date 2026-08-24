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
    # Aparte del polling general (métricas/QoS, cada device_poll_interval_seconds):
    # el estado online/offline de los clientes (tabla ARP) se quiere ver más al
    # día que eso, así que corre en su propio loop más frecuente.
    client_arp_poll_interval_seconds: int = 60

    # Colector NetFlow v5 (ver services/netflow/collector.py) para uso de
    # tráfico por cliente. netflow_public_host es la IP/host de este backend
    # que se le indica a cada Mikrotik como target de /ip/traffic-flow -- si
    # queda vacío, el poller no intenta auto-configurar ningún equipo.
    netflow_collector_port: int = 2055
    netflow_public_host: str = ""
    netflow_retention_days: int = 90

    # Reintento con backoff para las llamadas de red del poller (ver
    # app/workers/retry.py) -- compartido por polling de dispositivos y de
    # estado online de clientes, misma forma de "reintentar una llamada de
    # red". Los jobs diarios (facturación, purga de tráfico) usan
    # max_attempts=1: son batch/sensibles a reprocesamiento parcial, no
    # conviene reintentarlos a ciegas.
    poller_retry_max_attempts: int = 3
    poller_retry_backoff_base_seconds: float = 5.0
    poller_retry_backoff_max_seconds: float = 30.0
    daily_billing_max_attempts: int = 1
    traffic_maintenance_max_attempts: int = 1

    # Correo saliente para notificaciones al cliente (ver
    # app/services/notifications/email_provider.py). Credencial de
    # infraestructura, no una regla de negocio -- solo por .env, nunca
    # editable desde la web (a diferencia de BillingSettings). Si
    # smtp_host queda vacío, el envío falla con gracia y queda registrado
    # como intento fallido, no tumba el backend.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    # Push del navegador (Web Push / VAPID, ver
    # app/services/notifications/push_provider.py). Generar el par con
    # `python -m app.cli.generate_vapid_keys`. Mismo criterio que SMTP:
    # solo .env, se degrada con gracia si están vacías.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:soporte@example.com"

    # Pasarela de pago Wompi (ver app/services/wompi/). Credencial de
    # infraestructura, solo .env. wompi_api_base_url apunta a sandbox por
    # defecto a propósito -- pasar a producción es una decisión explícita,
    # no algo que pase por accidente al copiar un .env.example.
    wompi_public_key: str = ""
    wompi_private_key: str = ""
    wompi_integrity_secret: str = ""
    wompi_events_secret: str = ""
    wompi_api_base_url: str = "https://sandbox.wompi.co/v1"

    environment: str = "production"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
