"""Último recurso: acceso por MAC-Telnet cuando ni la IP guardada ni el
descubrimiento MNDP encuentran el equipo.

MAC-Telnet es un protocolo propietario de capa 2 (Ethernet crudo) que MikroTik
usa en Winbox para conectarse a un equipo que no tiene IP configurada. No se
reimplementa el protocolo (incluye una negociación criptográfica EC-SRP) desde
cero: en vez de eso, este módulo se apoya en el binario externo `mactelnet`
(https://github.com/haakonnessjoen/MAC-Telnet), controlado vía pexpect.

También maneja el cambio de contraseña obligatorio que RouterOS 7 exige en
el primer login tras un reset de fábrica (`/system reset-configuration`,
ver `reset_to_factory_defaults` en device_service.py): sin contraseña nueva
no hay forma de usar la API/SSH normal, así que `set_initial_password()`
completa ese flujo (el mismo diálogo "Change Password Now" de Winbox, pero
por consola) antes de que el resto de la app pueda tomar el control del
equipo por su vía habitual.

Tres problemas reales encontrados y resueltos aquí (no son teóricos — se
reprodujeron y depuraron con gdb y capturas de buffer crudo contra un equipo
real durante un incidente de recuperación):

1. El paquete `mactelnet-client` de los repos de Ubuntu (0.4.4, ~2011) no
   soporta la autenticación EC-SRP que RouterOS exige desde 6.43 en adelante
   — truena en cualquier intento de conexión real contra un equipo moderno.
   Por eso este módulo requiere una build propia desde el repo oficial (ver
   README) en vez de depender del paquete del sistema.
2. El cliente lee la variable de entorno TERM (mactelnet.c:235) y si no está
   definida hace strlen(NULL) — segfault. Los procesos lanzados por systemd
   (o por pexpect sin especificarlo) no tienen TERM seteada por defecto, así
   que se fija explícitamente al invocar el binario.
3. RouterOS envía primero una consulta de posición de cursor (`ESC [ 6n`,
   DSR) esperando una respuesta de terminal real, y su consola interactiva
   redibuja el prompt con colores ANSI en cada línea — un simple
   `pexpect.expect()` sobre el prompt cae en falsos positivos contra esos
   redibujados. Este módulo responde la consulta DSR manualmente y, para
   leer la salida de un comando, drena el buffer completo (en vez de
   confiar en un único match de prompt), limpia los códigos ANSI y filtra
   los ecos/prompts línea por línea.

Requisitos que NO están cubiertos por esta app y deben resolverse una sola
vez en el servidor (ver README):
  - El binario `mactelnet` compilado desde el repo oficial (no el paquete
    de Ubuntu — ver arriba) en `backend/bin/mactelnet`.
  - El binario con la capability CAP_NET_RAW (`setcap cap_net_raw+ep`) o
    ejecutado como root, porque MAC-Telnet necesita sockets crudos.
  - El servidor debe estar en el mismo segmento físico/VLAN que el Mikrotik:
    no funciona a través de un router/firewall que no reenvíe tráfico L2.

Si el binario no existe o falla por falta de permisos, se levanta
MacTelnetError y quien llama debe tratarlo igual que un fallo de SSH: no debe
tirar el proceso.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

# Preferimos el binario compilado desde el repo oficial (ver docstring del
# módulo): el paquete `mactelnet-client` de Ubuntu no soporta la
# autenticación EC-SRP que exige RouterOS >= 6.43 y falla en cualquier
# conexión real. Si no existe esa build local, caemos al binario del PATH
# del sistema (mejor eso que nada, aunque puede no funcionar).
_LOCAL_BINARY = Path(__file__).resolve().parents[3] / "bin" / "mactelnet"

_PROMPT = r"\[\S+@\S+\]\s*>\s*"
_LICENSE_PROMPT = "Do you want to see the software license"
_PASSWORD_CHANGE_PROMPT = "Change your password"
_DSR_QUERY = r"\x1b\[6n"
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_PROMPT_PREFIX = re.compile(r"^\[\S+@\S+\]\s*>\s*")


class MacTelnetError(Exception):
    pass


def _binary_path() -> str | None:
    if _LOCAL_BINARY.exists():
        return str(_LOCAL_BINARY)
    return shutil.which("mactelnet")


def is_available() -> bool:
    """True si hay un binario mactelnet utilizable (local o en el PATH)."""
    return _binary_path() is not None


def _drain(child, settle_time: float = 0.4, max_wait: float = 10.0) -> str:
    """Lee todo lo disponible hasta que no llegue nada nuevo por settle_time
    segundos. La consola de RouterOS redibuja con ANSI, así que no se puede
    confiar en un único match de prompt como señal de "ya terminó"."""
    import pexpect

    buf = ""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            chunk = child.read_nonblocking(size=4096, timeout=settle_time)
        except (pexpect.exceptions.TIMEOUT, pexpect.exceptions.EOF):
            break
        if not chunk:
            break
        buf += chunk
    return buf


def _clean_output(raw: str, command: str) -> str:
    """Quita colores ANSI y filtra líneas que son solo eco del comando o el
    prompt, dejando únicamente el contenido real de la respuesta."""
    text = _ANSI_ESCAPE.sub("", raw)
    cmd = command.strip()
    lines = []
    for line in re.split(r"[\r\n]+", text):
        line = _PROMPT_PREFIX.sub("", line).strip()
        if not line or line == cmd:
            continue
        lines.append(line)
    return "\n".join(lines)


def _respond_to_dsr(child, timeout: float = 5.0) -> None:
    """RouterOS pregunta la posición del cursor (DSR) y espera respuesta de
    una terminal real antes de continuar. Puede aparecer más de una vez
    (ej. en el flujo de cambio de contraseña, que redibuja toda la pantalla)."""
    import pexpect

    while child.expect([_DSR_QUERY, pexpect.TIMEOUT], timeout=timeout) == 0:
        child.send("\x1b[24;80R")


def _spawn(binary: str, mac_address: str, username: str, password: str, timeout: float):
    import pexpect

    env = dict(os.environ)
    env.setdefault("TERM", "xterm")  # o strlen(NULL) truena — ver docstring del módulo.

    return pexpect.spawn(
        binary,
        [mac_address, "-u", username, "-p", password, "-t", str(int(timeout))],
        timeout=timeout,
        encoding="utf-8",
        env=env,
    )


def _login(child, timeout: float) -> str:
    """Lleva la sesión desde la conexión inicial hasta un estado conocido.

    Devuelve "prompt" si llegó al prompt normal de RouterOS, o
    "password_change" si el equipo exige cambiar la contraseña antes de
    continuar (ver set_initial_password). Levanta MacTelnetError en
    cualquier otro caso (login rechazado, timeout, crash del binario)."""
    import pexpect

    _respond_to_dsr(child)

    index = child.expect(
        [
            "Login failed",
            "Connection timed out",
            _LICENSE_PROMPT,
            _PASSWORD_CHANGE_PROMPT,
            _PROMPT,
            pexpect.EOF,
            pexpect.TIMEOUT,
        ],
    )
    if index == 0:
        raise MacTelnetError("Login MAC-Telnet rechazado (usuario/contraseña incorrectos).")
    if index == 1:
        raise MacTelnetError("MAC-Telnet: tiempo de espera agotado (¿el equipo está en la misma red L2?).")
    if index == 2:
        child.sendline("n")
        _respond_to_dsr(child)  # el flujo de cambio de contraseña vuelve a preguntar DSR al redibujar
        index = child.expect([_PASSWORD_CHANGE_PROMPT, _PROMPT, pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
        index += 3  # realinea: 0=password_change->3, 1=_PROMPT->4, 2=EOF->5, 3=TIMEOUT->6
    if index == 3:
        return "password_change"
    if index == 4:
        return "prompt"
    if index == 5:
        child.close()
        if child.signalstatus is not None:
            raise MacTelnetError(
                f"El binario mactelnet terminó de forma anormal "
                f"(señal {child.signalstatus}, posible crash de esta build), "
                "no por un problema de la app."
            )
        raise MacTelnetError("MAC-Telnet cerró la conexión sin mostrar un prompt reconocible.")
    raise MacTelnetError("MAC-Telnet no respondió a tiempo esperando un prompt.")


def run_command(mac_address: str, username: str, password: str, command: str, timeout: float = 15.0) -> str:
    """Abre una sesión MAC-Telnet, envía un comando y devuelve la salida.

    Requiere el paquete `pexpect` (ya declarado en requirements.txt) y un
    binario `mactelnet` utilizable con CAP_NET_RAW. Si cualquiera de los dos
    falta, levanta MacTelnetError con un mensaje claro en vez de fallar de
    forma críptica.
    """
    binary = _binary_path()
    if binary is None:
        raise MacTelnetError(
            "No hay un binario 'mactelnet' utilizable en este servidor "
            "(ni en backend/bin/ ni en el PATH). MAC-Telnet no está "
            "disponible como último recurso."
        )

    try:
        import pexpect  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise MacTelnetError("El paquete 'pexpect' no está instalado.") from exc

    child = None
    try:
        child = _spawn(binary, mac_address, username, password, timeout)
        state = _login(child, timeout)
        if state == "password_change":
            raise MacTelnetError(
                "El equipo exige cambiar la contraseña antes de aceptar comandos "
                "(típico tras un reset de fábrica). Usa set_initial_password() primero."
            )

        # Descarta cualquier resto del banner/prompt inicial antes de mandar el comando.
        _drain(child, settle_time=0.3, max_wait=2.0)

        child.sendline(command)
        raw = _drain(child, settle_time=0.5, max_wait=timeout)
        return _clean_output(raw, command)
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, MacTelnetError):
            raise
        raise MacTelnetError(f"Fallo de MAC-Telnet: {exc}") from exc
    finally:
        if child is not None and child.isalive():
            try:
                child.sendline("/quit")
                child.close(force=True)
            except Exception:  # noqa: BLE001
                pass


def set_initial_password(mac_address: str, username: str, old_password: str, new_password: str, timeout: float = 20.0) -> None:
    """Completa el cambio de contraseña obligatorio que RouterOS 7 exige en
    el primer login tras un reset de fábrica (mismo diálogo "Change Password
    Now" de Winbox, hecho por consola). `old_password` normalmente es ""
    (el usuario admin de fábrica no tiene contraseña).

    Tras esta llamada, `new_password` queda activa y el equipo acepta
    comandos normales por API/SSH/MAC-Telnet — quien llame debe guardar esa
    contraseña (cifrada) en el registro del equipo.
    """
    binary = _binary_path()
    if binary is None:
        raise MacTelnetError(
            "No hay un binario 'mactelnet' utilizable en este servidor "
            "(ni en backend/bin/ ni en el PATH)."
        )

    try:
        import pexpect
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise MacTelnetError("El paquete 'pexpect' no está instalado.") from exc

    child = None
    try:
        child = _spawn(binary, mac_address, username, old_password, timeout)
        state = _login(child, timeout)
        if state == "prompt":
            raise MacTelnetError(
                "El equipo no está pidiendo cambio de contraseña — ¿ya se completó antes? "
                "Usa run_command()/get_identity() con la contraseña ya vigente."
            )

        child.sendline(new_password)
        _respond_to_dsr(child)
        idx = child.expect(["retype", "repeat", pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
        if idx >= 2:
            raise MacTelnetError("No se pudo completar el cambio de contraseña (no pidió confirmación).")

        child.sendline(new_password)
        _respond_to_dsr(child)
        idx2 = child.expect(["Password changed", _PROMPT, pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
        if idx2 >= 2:
            raise MacTelnetError("No se pudo confirmar el cambio de contraseña (el equipo cortó la sesión).")
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, MacTelnetError):
            raise
        raise MacTelnetError(f"Fallo al cambiar la contraseña por MAC-Telnet: {exc}") from exc
    finally:
        if child is not None and child.isalive():
            try:
                child.sendline("/quit")
                child.close(force=True)
            except Exception:  # noqa: BLE001
                pass


def get_identity(mac_address: str, username: str, password: str) -> str:
    output = run_command(mac_address, username, password, "/system identity print")
    for line in output.splitlines():
        if line.strip().startswith("name:"):
            return line.split("name:", 1)[1].strip()
    return ""
