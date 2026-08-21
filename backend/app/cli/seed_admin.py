"""Crea (o actualiza la contraseña de) el primer usuario admin del panel.

Uso:
    python -m app.cli.seed_admin admin@example.com "Nombre Completo" "contraseña-segura"
"""

import sys

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def main() -> None:
    if len(sys.argv) != 4:
        print(__doc__)
        raise SystemExit(1)

    email, full_name, password = sys.argv[1], sys.argv[2], sys.argv[3]

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.hashed_password = hash_password(password)
            user.full_name = full_name
            user.role = UserRole.ADMIN
            user.is_active = True
            print(f"Usuario existente actualizado: {email}")
        else:
            user = User(
                email=email,
                full_name=full_name,
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(user)
            print(f"Usuario admin creado: {email}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
