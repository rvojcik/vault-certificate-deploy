"""
Unit tests for the cert_ops module — no Vault required, sub-second.

Demonstrates testing pure logic in isolation: generate a self-signed cert
in-memory with `cryptography`, then exercise certificate_check against it.
"""

from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from vault_certificate_deploy import cert_ops


def _make_cert(days_valid: int) -> tuple[bytes, bytes]:
    """Generate self-signed cert + key. Returns (cert_pem, key_pem)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=days_valid))
        .sign(key, hashes.SHA256())
    )
    return (
        cert.public_bytes(serialization.Encoding.PEM),
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )


@pytest.fixture
def cert_files(tmp_path):
    """Factory: write cert+key of given lifetime to tmp_path, return paths."""

    def _factory(days_valid: int):
        cert_pem, key_pem = _make_cert(days_valid)
        crt = tmp_path / "test.crt"
        key = tmp_path / "test.key"
        crt.write_bytes(cert_pem)
        key.write_bytes(key_pem)
        return crt, key

    return _factory


def test_check_returns_false_when_below_threshold(cert_files):
    """Cert valid 1 day, threshold 7 days → renewal required."""
    crt, key = cert_files(days_valid=1)
    assert cert_ops.certificate_check("t", str(crt), str(key), 7 * 86400) is False


def test_check_returns_true_when_above_threshold(cert_files):
    """Cert valid 30 days, threshold 7 days → no renewal."""
    crt, key = cert_files(days_valid=30)
    assert cert_ops.certificate_check("t", str(crt), str(key), 7 * 86400) is True


def test_check_returns_false_when_files_missing(tmp_path):
    """Missing cert file → renewal required."""
    result = cert_ops.certificate_check(
        "t",
        str(tmp_path / "missing.crt"),
        str(tmp_path / "missing.key"),
        7 * 86400,
    )
    assert result is False


@pytest.mark.parametrize(
    "days,threshold_days,expected",
    [
        (1, 7, False),
        (10, 7, True),
        (7, 7, False),  # equal — strict less-than means renew
        (365, 30, True),
    ],
)
def test_check_threshold_boundaries(cert_files, days, threshold_days, expected):
    """parametrize keeps a matrix of cases readable as a single test."""
    crt, key = cert_files(days_valid=days)
    result = cert_ops.certificate_check(
        "t", str(crt), str(key), threshold_days * 86400
    )
    assert result is expected
