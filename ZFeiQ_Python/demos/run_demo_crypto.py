"""Demo for CryptoService: generate RSA keys, symmetric key, encrypt/decrypt."""
from zfeiq_core.services.crypto import CryptoService


def main():
    cs = CryptoService()
    priv, pub = cs.generate_keypair(2048)
    print("Generated RSA keys: priv len", len(priv), "pub len", len(pub))

    # symmetric
    key = b"\x00" * 32  # demo key (NOT for production)
    data = b"hello symmetric world"
    blob = cs.symmetric_encrypt(data, key)
    pt = cs.symmetric_decrypt(blob, key)
    print("Symmetric decrypt ok:", pt)

    # RSA encrypt small payload
    secret = b"a small secret"
    ct = cs.rsa_encrypt(secret, pub)
    pt2 = cs.rsa_decrypt(ct, priv)
    print("RSA decrypt ok:", pt2)


if __name__ == "__main__":
    main()
