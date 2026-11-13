"""Print VAPID keys for Web Push:  python scripts/gen_vapid.py
Put the three values in your environment (never commit the private key)."""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def generate():
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return b64(private), b64(public)


if __name__ == "__main__":
    priv, pub = generate()
    print(f"VAPID_PRIVATE_KEY={priv}\nVAPID_PUBLIC_KEY={pub}\nVAPID_SUBJECT=mailto:you@example.com")
