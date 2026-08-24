"""Genera un par de claves VAPID para Web Push (ver
app/services/notifications/push_provider.py) y las imprime en el formato
base64url compacto que espera .env (VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY).

Uso:
    python -m app.cli.generate_vapid_keys
"""

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid02
from py_vapid.utils import b64urlencode


def main() -> None:
    vapid = Vapid02()
    vapid.generate_keys()

    public_raw = vapid.public_key.public_bytes(
        encoding=Encoding.X962, format=PublicFormat.UncompressedPoint
    )
    private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")

    print("VAPID_PUBLIC_KEY=" + b64urlencode(public_raw))
    print("VAPID_PRIVATE_KEY=" + b64urlencode(private_raw))


if __name__ == "__main__":
    main()
