"""Wrapper delgado sobre paramiko: acceso SSH de respaldo/diagnóstico a RouterOS."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import paramiko


class RouterOsSshError(Exception):
    pass


@contextmanager
def ssh_connection(
    host: str,
    username: str,
    password: str,
    port: int = 22,
    timeout: float = 8.0,
) -> Iterator[paramiko.SSHClient]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
    except (paramiko.SSHException, OSError) as exc:
        raise RouterOsSshError(str(exc)) from exc

    try:
        yield client
    finally:
        client.close()


def run_command(client: paramiko.SSHClient, command: str, timeout: float = 10.0) -> str:
    try:
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        output = stdout.read().decode(errors="replace")
        error = stderr.read().decode(errors="replace")
    except paramiko.SSHException as exc:
        raise RouterOsSshError(str(exc)) from exc
    if error.strip():
        raise RouterOsSshError(error.strip())
    return output


def get_identity(client: paramiko.SSHClient) -> str:
    output = run_command(client, "/system identity print")
    for line in output.splitlines():
        if "name:" in line:
            return line.split("name:", 1)[1].strip()
    return ""


def export_config(client: paramiko.SSHClient) -> str:
    return run_command(client, "/export", timeout=30)


def reboot(client: paramiko.SSHClient) -> None:
    try:
        client.exec_command("/system reboot")
    except paramiko.SSHException:
        # El router corta la sesión SSH al reiniciar; es el comportamiento esperado.
        pass
