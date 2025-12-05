# NZFeiQ/core/crypto.py
import os
import base64
from typing import Tuple, Optional, Any
import importlib.util as _ilu

_CRYPTO_AVAILABLE = _ilu.find_spec("cryptography") is not None

def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode('ascii')

def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode('ascii'))

# --- X25519 (ECDH) ---
def generate_x25519_keypair() -> Tuple[Any, bytes]:
    """生成 X25519 密钥对。返回 (私钥对象, 公钥bytes 32B)"""
    if not _CRYPTO_AVAILABLE: raise RuntimeError("Missing cryptography")
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives import serialization
    priv = x25519.X25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return priv, pub_bytes

def load_x25519_private_key(data: bytes) -> Any:
    """从 bytes 加载私钥"""
    if not _CRYPTO_AVAILABLE: raise RuntimeError("Missing cryptography")
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives import serialization
    return x25519.X25519PrivateKey.from_private_bytes(data)

def dump_x25519_private_key(priv: Any) -> bytes:
    """导出私钥为 bytes (32B)"""
    from cryptography.hazmat.primitives import serialization
    return priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )

def derive_x25519_shared(local_priv: Any, peer_pub_bytes: bytes) -> bytes:
    if not _CRYPTO_AVAILABLE: raise RuntimeError("Missing cryptography")
    from cryptography.hazmat.primitives.asymmetric import x25519
    peer_pub = x25519.X25519PublicKey.from_public_bytes(peer_pub_bytes)
    return local_priv.exchange(peer_pub)

# --- ChaCha20-Poly1305 (AEAD) ---
def chacha20_encrypt(key32: bytes, plaintext: bytes, nonce12: bytes, aad: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    if len(key32) != 32 or len(nonce12) != 12: raise ValueError("Invalid params")
    if not _CRYPTO_AVAILABLE: raise RuntimeError("Missing cryptography")
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    
    chacha = ChaCha20Poly1305(key32)
    ct_with_tag = chacha.encrypt(nonce12, plaintext, aad)
    return ct_with_tag[:-16], ct_with_tag[-16:]

def chacha20_decrypt(key32: bytes, nonce12: bytes, ciphertext: bytes, tag16: bytes, aad: Optional[bytes] = None) -> bytes:
    if not _CRYPTO_AVAILABLE: raise RuntimeError("Missing cryptography")
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    
    chacha = ChaCha20Poly1305(key32)
    return chacha.decrypt(nonce12, ciphertext + tag16, aad)

# --- HKDF (必须保留) ---
def hkdf_sha256(ikm: bytes, info: bytes, length: int = 32, salt: Optional[bytes] = None) -> bytes:
    if not _CRYPTO_AVAILABLE: raise RuntimeError("Missing cryptography")
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes
    
    if salt is None: salt = b"\x00" * 32
    kdf = HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info)
    return kdf.derive(ikm)