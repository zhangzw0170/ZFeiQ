from typing import Tuple, Optional
import os

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes as _hashes
import hashlib
from pathlib import Path


class CryptoService:
    """Provides basic RSA keypair generation and AES‑GCM symmetric encryption.

    API:
    - generate_keypair(bits=2048) -> (priv_pem, pub_pem)
    - rsa_encrypt(data, pub_pem) -> bytes
    - rsa_decrypt(data, priv_pem) -> bytes
    - symmetric_encrypt(data, key) -> bytes (nonce || ciphertext)
    - symmetric_decrypt(blob, key) -> bytes
    """

    def generate_keypair(self, bits: int = 2048) -> Tuple[bytes, bytes]:
        priv = rsa.generate_private_key(public_exponent=65537, key_size=bits)
        priv_pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub = priv.public_key()
        pub_pem = pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return priv_pem, pub_pem

    def rsa_encrypt(self, data: bytes, pub_pem: bytes) -> bytes:
        pub = serialization.load_pem_public_key(pub_pem)
        ct = pub.encrypt(
            data,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
        return ct

    def rsa_decrypt(self, data: bytes, priv_pem: bytes) -> bytes:
        priv = serialization.load_pem_private_key(priv_pem, password=None)
        pt = priv.decrypt(
            data,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
        return pt

    def symmetric_encrypt(self, data: bytes, key: bytes) -> bytes:
        """Encrypt with AES-GCM. Returns nonce || ciphertext || tag (concatenated).

        The caller is responsible for sharing the `key` (32 bytes for AES-256).
        """
        if len(key) not in (16, 24, 32):
            raise ValueError("Key must be 16/24/32 bytes for AES")
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, data, associated_data=None)
        # ct already contains ciphertext || tag
        return nonce + ct

    def symmetric_decrypt(self, blob: bytes, key: bytes) -> bytes:
        if len(key) not in (16, 24, 32):
            raise ValueError("Key must be 16/24/32 bytes for AES")
        if len(blob) < 12 + 16:
            raise ValueError("Invalid blob")
        nonce = blob[:12]
        ct = blob[12:]
        aesgcm = AESGCM(key)
        pt = aesgcm.decrypt(nonce, ct, associated_data=None)
        return pt

    # Persistence helpers
    def save_private_key(self, priv_pem: bytes, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # write private key with restrictive permissions when possible
        p.write_bytes(priv_pem)

    def load_private_key(self, path: str) -> Optional[bytes]:
        p = Path(path)
        if not p.exists():
            return None
        return p.read_bytes()

    def save_public_key(self, pub_pem: bytes, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(pub_pem)

    def load_public_key(self, path: str) -> Optional[bytes]:
        p = Path(path)
        if not p.exists():
            return None
        return p.read_bytes()

    def fingerprint(self, pub_pem: bytes) -> str:
        # return hex sha256 fingerprint of public key bytes
        h = hashlib.sha256(pub_pem).hexdigest()
        # format as groups for readability
        return ":".join([h[i : i + 2] for i in range(0, len(h), 2)])
