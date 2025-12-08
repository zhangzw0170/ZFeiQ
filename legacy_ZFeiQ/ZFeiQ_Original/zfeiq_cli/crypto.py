import os
import base64
from typing import Tuple, Optional, cast
import importlib.util as _ilu

"""
Minimal wrapper for RSA (OAEP-SHA256), AES-256-GCM and HKDF-SHA256.
This module requires the `cryptography` package. PyCryptodome support
has been intentionally removed; if `cryptography` is not available
an explicit RuntimeError is raised with installation guidance.
"""

# 仅使用 cryptography 后端；不存在则提示用户安装。
_CRYPTO_AVAILABLE = _ilu.find_spec("cryptography") is not None


def generate_rsa_keypair(bits: int = 3072) -> Tuple[bytes, bytes]:
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("Missing dependency: install the 'cryptography' package")
    from cryptography.hazmat.primitives.asymmetric import rsa  # local import
    from cryptography.hazmat.primitives import serialization  # local import
    from cryptography.hazmat.backends import default_backend  # local import
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits, backend=default_backend())
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv_pem, pub_pem


def rsa_encrypt(pub_pem: bytes, data: bytes) -> bytes:
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("Missing dependency: install the 'cryptography' package")
    from cryptography.hazmat.primitives import serialization, hashes  # local import
    from cryptography.hazmat.primitives.asymmetric import padding  # local import
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey  # for cast
    pub_obj = serialization.load_pem_public_key(pub_pem)
    pub = cast(RSAPublicKey, pub_obj)
    return pub.encrypt(data, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))  # type: ignore[arg-type]


def rsa_decrypt(priv_pem: bytes, data: bytes) -> bytes:
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("Missing dependency: install the 'cryptography' package")
    from cryptography.hazmat.primitives import serialization, hashes  # local import
    from cryptography.hazmat.primitives.asymmetric import padding  # local import
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey  # for cast
    priv_obj = serialization.load_pem_private_key(priv_pem, password=None)
    priv = cast(RSAPrivateKey, priv_obj)
    return priv.decrypt(data, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))  # type: ignore[arg-type]


def aes_gcm_encrypt(key32: bytes, plaintext: bytes, aad: Optional[bytes] = None, nonce: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
    """Return (nonce12, ciphertext, tag16).

    If `nonce` is provided (12 bytes), use it; otherwise generate a random 12-byte nonce.
    """
    if len(key32) != 32:
        raise ValueError("AES-GCM key must be 32 bytes (256-bit)")
    nonce = nonce if (isinstance(nonce, (bytes, bytearray)) and len(nonce) == 12) else os.urandom(12)
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("Missing dependency: install the 'cryptography' package")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # local import
    aead = AESGCM(key32)
    ct = aead.encrypt(nonce, plaintext, aad)
    # cryptography returns ct|tag at the end; split tag16
    tag = ct[-16:]
    c = ct[:-16]
    return nonce, c, tag


def aes_gcm_decrypt(key32: bytes, nonce12: bytes, ciphertext: bytes, tag16: bytes, aad: Optional[bytes] = None) -> bytes:
    if len(key32) != 32:
        raise ValueError("AES-GCM key must be 32 bytes (256-bit)")
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("Missing dependency: install the 'cryptography' package")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # local import
    aead = AESGCM(key32)
    return aead.decrypt(nonce12, ciphertext + tag16, aad)


def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode('ascii')


def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode('ascii'))


def hkdf_sha256(ikm: bytes, info: bytes = b"zfeiq-aes256gcm", length: int = 32, salt: Optional[bytes] = None) -> bytes:
    """HKDF-SHA256 key derivation.

    Tries cryptography first, and finally a minimal HMAC-based fallback.
    """
    if not isinstance(ikm, (bytes, bytearray)):
        raise TypeError("ikm must be bytes")
    if salt is None:
        salt = b"\x00" * 32
    # Prefer cryptography
    if _CRYPTO_AVAILABLE:
        try:
            from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # local import
            from cryptography.hazmat.primitives import hashes  # local import
            kdf = HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info)
            return kdf.derive(bytes(ikm))
        except Exception:
            # Fall through to minimal HMAC-based HKDF implementation
            pass
    # Minimal fallback per RFC5869
    import hmac, hashlib
    def _hmac_sha256(key: bytes, data: bytes) -> bytes:
        return hmac.new(key, data, hashlib.sha256).digest()
    prk = _hmac_sha256(salt or b"", bytes(ikm))
    t = b""
    okm = b""
    counter = 1
    while len(okm) < length:
        t = _hmac_sha256(prk, t + info + bytes([counter]))
        okm += t
        counter += 1
    return okm[:length]
