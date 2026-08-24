"""Generación de fichas HotSpot prepago -- ver Fase 5e en el plan del
proyecto para el contexto completo (por qué esta fase no empuja nada a un
Mikrotik real todavía)."""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy.orm import Session

from app.models.hotspot import HotspotProfile, HotspotVoucher, HotspotVoucherStatus

# Sin 0/O, 1/I/L -- una ficha se dicta/teclea de memoria desde un papel, a
# diferencia de una API key que se copia/pega, así que la ambigüedad visual
# de esos caracteres es un problema real acá.
VOUCHER_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
VOUCHER_CODE_LENGTH = 8


def generate_voucher_code() -> str:
    return "".join(secrets.choice(VOUCHER_CODE_ALPHABET) for _ in range(VOUCHER_CODE_LENGTH))


def create_voucher_batch(db: Session, profile: HotspotProfile, quantity: int) -> list[HotspotVoucher]:
    """Genera `quantity` fichas UNUSED con precio congelado del perfil y un
    batch_id compartido para poder imprimir el lote completo de una. Una
    colisión de código es astronómicamente improbable (32^8 combinaciones)
    pero se valida contra la base igual, mismo espíritu defensivo que el
    resto del proyecto."""
    batch_id = uuid.uuid4()
    existing_codes = {row[0] for row in db.query(HotspotVoucher.code).all()}
    vouchers: list[HotspotVoucher] = []
    for _ in range(quantity):
        code = generate_voucher_code()
        while code in existing_codes:
            code = generate_voucher_code()
        existing_codes.add(code)
        vouchers.append(
            HotspotVoucher(
                profile_id=profile.id,
                code=code,
                price=profile.price,
                batch_id=batch_id,
                status=HotspotVoucherStatus.UNUSED,
            )
        )
    db.add_all(vouchers)
    db.commit()
    for voucher in vouchers:
        db.refresh(voucher)
    return vouchers
