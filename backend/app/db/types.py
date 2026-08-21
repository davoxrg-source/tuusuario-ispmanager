from sqlalchemy import Enum


def pg_enum(enum_cls, name: str) -> Enum:
    """Enum de Postgres que persiste el .value de los enums de Python (minúsculas),
    en vez del .name por defecto de SQLAlchemy (mayúsculas)."""
    return Enum(enum_cls, name=name, values_callable=lambda cls: [member.value for member in cls])
