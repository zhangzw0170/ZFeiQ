import pytest

# 简单的测试模板：验证签名/验证 API 的存在性与基本行为
# 实际实现需要 core.crypto 中提供 sign_bytes / verify_bytes

try:
    from NZFeiQ.core import crypto
except Exception:
    crypto = None


def test_sign_verify_present():
    assert crypto is not None, "core.crypto 模块不可用"
    assert hasattr(crypto, 'sign_bytes') and callable(crypto.sign_bytes)
    assert hasattr(crypto, 'verify_bytes') and callable(crypto.verify_bytes)


def test_sign_verify_roundtrip():
    # 若实现了 sign/verify 则做一次 roundtrip 测试
    if crypto is None:
        pytest.skip("core.crypto 未实现")

    msg = b"test-ephemeral-pub"
    # 需要一个测试私钥/公钥。若 core.crypto 提供 keygen 接口则使用之
    if hasattr(crypto, 'generate_ed25519_keypair'):
        priv, pub = crypto.generate_ed25519_keypair()
    else:
        pytest.skip("没有可用的 keygen 接口用于测试")

    sig = crypto.sign_bytes(priv, msg)
    assert isinstance(sig, (bytes, bytearray))
    ok = crypto.verify_bytes(pub, msg, sig)
    assert ok is True
