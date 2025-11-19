import os
import base64
from typing import Tuple, Optional, cast
import importlib.util as _ilu

# This module provides a minimal wrapper for RSA (OAEP-SHA256) and AES-256-GCM.
# It tries to use 'cryptography' first, then fallbacks to 'PyCryptodome'.

# 后端探测（仅用于选择，具体库在函数内部按需导入，避免“可能未绑定”提示）
if _ilu.find_spec("cryptography") is not None:
    _CRYPTO_BACKEND = "cryptography"
elif _ilu.find_spec("Crypto") is not None:
    _CRYPTO_BACKEND = "pycryptodome"
else:
    _CRYPTO_BACKEND = None


def generate_rsa_keypair(bits: int = 3072) -> Tuple[bytes, bytes]:
    if _CRYPTO_BACKEND == "cryptography":
        from cryptography.hazmat.primitives.asymmetric import rsa  # local import
        from cryptography.hazmat.primitives import serialization  # local import
        key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
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
    elif _CRYPTO_BACKEND == "pycryptodome":
        from Crypto.PublicKey import RSA as _RSA  # local import
        key = _RSA.generate(bits)
        priv_pem = key.export_key(format='PEM')
        pub_pem = key.publickey().export_key(format='PEM')
        return priv_pem, pub_pem
    else:
        raise RuntimeError("No crypto backend: install 'cryptography' or 'pycryptodome'")


def rsa_encrypt(pub_pem: bytes, data: bytes) -> bytes:
    if _CRYPTO_BACKEND == "cryptography":
        from cryptography.hazmat.primitives import serialization, hashes  # local import
        from cryptography.hazmat.primitives.asymmetric import padding  # local import
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey  # for cast
        pub_obj = serialization.load_pem_public_key(pub_pem)
        pub = cast(RSAPublicKey, pub_obj)
        return pub.encrypt(data, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))  # type: ignore[arg-type]
    elif _CRYPTO_BACKEND == "pycryptodome":
        from Crypto.PublicKey import RSA as _RSA  # local import
        from Crypto.Cipher import PKCS1_OAEP  # local import
        from Crypto.Hash import SHA256  # local import
        pub = _RSA.import_key(pub_pem)
        cipher = PKCS1_OAEP.new(pub, hashAlgo=SHA256)
        return cipher.encrypt(data)
    else:
        raise RuntimeError("No crypto backend")


def rsa_decrypt(priv_pem: bytes, data: bytes) -> bytes:
    if _CRYPTO_BACKEND == "cryptography":
        from cryptography.hazmat.primitives import serialization, hashes  # local import
        from cryptography.hazmat.primitives.asymmetric import padding  # local import
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey  # for cast
        priv_obj = serialization.load_pem_private_key(priv_pem, password=None)
        priv = cast(RSAPrivateKey, priv_obj)
        return priv.decrypt(data, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))  # type: ignore[arg-type]
    elif _CRYPTO_BACKEND == "pycryptodome":
        from Crypto.PublicKey import RSA as _RSA  # local import
        from Crypto.Cipher import PKCS1_OAEP  # local import
        from Crypto.Hash import SHA256  # local import
        priv = _RSA.import_key(priv_pem)
        cipher = PKCS1_OAEP.new(priv, hashAlgo=SHA256)
        return cipher.decrypt(data)
    else:
        raise RuntimeError("No crypto backend")


def aes_gcm_encrypt(key32: bytes, plaintext: bytes, aad: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
    """Return (nonce12, ciphertext, tag16)."""
    if len(key32) != 32:
        raise ValueError("AES-GCM key must be 32 bytes (256-bit)")
    nonce = os.urandom(12)
    if _CRYPTO_BACKEND == "cryptography":
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # local import
        aead = AESGCM(key32)
        ct = aead.encrypt(nonce, plaintext, aad)
        # cryptography returns ct|tag at the end; split tag16
        tag = ct[-16:]
        c = ct[:-16]
        return nonce, c, tag
    elif _CRYPTO_BACKEND == "pycryptodome":
        from Crypto.Cipher import AES  # local import
        cipher = AES.new(key32, AES.MODE_GCM, nonce=nonce)
        if aad:
            cipher.update(aad)
        c, tag = cipher.encrypt_and_digest(plaintext)
        return nonce, c, tag
    else:
        raise RuntimeError("No crypto backend")


def aes_gcm_decrypt(key32: bytes, nonce12: bytes, ciphertext: bytes, tag16: bytes, aad: Optional[bytes] = None) -> bytes:
    if len(key32) != 32:
        raise ValueError("AES-GCM key must be 32 bytes (256-bit)")
    if _CRYPTO_BACKEND == "cryptography":
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # local import
        aead = AESGCM(key32)
        return aead.decrypt(nonce12, ciphertext + tag16, aad)
    elif _CRYPTO_BACKEND == "pycryptodome":
        from Crypto.Cipher import AES  # local import
        cipher = AES.new(key32, AES.MODE_GCM, nonce=nonce12)
        if aad:
            cipher.update(aad)
        return cipher.decrypt_and_verify(ciphertext, tag16)
    else:
        raise RuntimeError("No crypto backend")


def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode('ascii')


def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode('ascii'))
