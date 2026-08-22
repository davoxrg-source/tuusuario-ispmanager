"""Último recurso: acceso por MAC-Telnet cuando ni la IP guardada ni el
descubrimiento MNDP encuentran el equipo.

MAC-Telnet es un protocolo propietario de capa 2 (Ethernet crudo) que MikroTik
usa en Winbox para conectarse a un equipo que no tiene IP configurada. No se
reimplementa el protocolo (incluye un handshake con desafío MD5) desde cero:
en vez de eso, este módulo se apoya en el binario externo `mactelnet`
(https://github.com/haakonnessjoen/MAC-Telnet), controlado vía pexpect para
enviar un comando de una sola línea y capturar la salida de texto, con una
interfaz equivalente a la de ssh_client.run_command.

Requisitos que NO están cubiertos por esta app y deben resolverse una sola
vez en el servidor (ver README):
  - El binario `mactelnet` instalado (paquete del sistema o compilado).
  - El binario con la capability CAP_NET_RAW (`setcap cap_net_raw+ep`) o
    ejecutado como root, porque MAC-Telnet necesita sockets crudos.
  - El servidor debe estar en el mismo segmento físico/VLAN que el Mikrotik:
    no funciona a través de un router/firewall que no reenvíe tráfico L2.

Si el binario no existe o falla por falta de permisos, se levanta
MacTelnetError y quien llama debe tratarlo igual que un fallo de SSH: no debe
tirar el proceso.
"""

from __future__ import annotations

import shutil

MACTELNET_BINARY = "mactelnet"
_PROMPT_MARKERS = ("] >", "> ")


class MacTelnetError(Exception):
    pass


def is_available() -> bool:
    """True si el binario mactelnet está instalado en el PATH del sistema."""
    return shutil.which(MACTELNET_BINARY) is not None


def run_command(mac_address: str, username: str, password: str, command: str, timeout: float = 15.0) -> str:
    """Abre una sesión MAC-Telnet, envía un comando y devuelve la salida.

    Requiere el paquete `pexpect` (ya declarado en requirements.txt) y el
    binario externo `mactelnet` instalado con CAP_NET_RAW. Si cualquiera de
    los dos falta, levanta MacTelnetError con un mensaje claro en vez de
    fallar de forma críptica.
    """
    if not is_available():
        raise MacTelnetError(
            f"El binario '{MACTELNET_BINARY}' no está instalado en este servidor. "
            "MAC-Telnet no está disponible como último recurso."
        )

    try:
        import pexpect
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise MacTelnetError("El paquete 'pexpect' no está instalado.") from exc

    child = None
    try:
        child = pexpect.spawn(
            MACTELNET_BINARY,
            [mac_address, "-u", username, "-p", password],
            timeout=timeout,
            encoding="utf-8",
        )
        eof_index = len(_PROMPT_MARKERS) + 2
        timeout_index = eof_index + 1
        index = child.expect(
            ["Login failed", "Connection timed out", *_PROMPT_MARKERS, pexpect.EOF, pexpect.TIMEOUT],
        )
        if index == 0:
            raise MacTelnetError("Login MAC-Telnet rechazado (usuario/contraseña incorrectos).")
        if index == 1:
            raise MacTelnetError("MAC-Telnet: tiempo de espera agotado (¿el equipo está en la misma red L2?).")
        if index == eof_index:
            # El proceso mactelnet terminó antes de mostrar un prompt. Si fue por
            # una señal (crash/segfault del binario) lo decimos explícitamente,
            # en vez de un genérico "no reconoció el prompt" que confunde el
            # diagnóstico (esto se ha visto con mactelnet-client 0.4.4 de Ubuntu).
            child.close()
            if child.signalstatus is not None:
                raise MacTelnetError(
                    f"El binario '{MACTELNET_BINARY}' terminó de forma anormal "
                    f"(señal {child.signalstatus}, posible crash/segfault de esta versión del binario), "
                    "no por un problema de la app."
                )
            raise MacTelnetError("MAC-Telnet cerró la conexión sin mostrar un prompt reconocible.")
        if index == timeout_index:
            raise MacTelnetError("MAC-Telnet no respondió a tiempo esperando un prompt.")

        child.sendline(command)
        child.expect(_PROMPT_MARKERS, timeout=timeout)
        output = child.before or ""
        return output.strip()
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


def get_identity(mac_address: str, username: str, password: str) -> str:
    output = run_command(mac_address, username, password, "/system identity print")
    for line in output.splitlines():
        if "name:" in line:
            return line.split("name:", 1)[1].strip()
    return ""
