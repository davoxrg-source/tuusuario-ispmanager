import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> tuple[bool, str | None]:
    """Manda un correo por SMTP -- stdlib, sin dependencia nueva. Devuelve
    (False, "SMTP no configurado") sin intentar nada si smtp_host está
    vacío, mismo espíritu de degradación con gracia que el colector NetFlow
    en main.py (no configurado no es lo mismo que roto)."""
    settings = get_settings()
    if not settings.smtp_host:
        return False, "SMTP no configurado."

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = to
    message.set_content(body)

    try:
        smtp_cls = smtplib.SMTP_SSL if settings.smtp_port == 465 else smtplib.SMTP
        with smtp_cls(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls and settings.smtp_port != 465:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return True, None
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo mandar el correo a %s: %s", to, exc)
        return False, str(exc)[:2000]
