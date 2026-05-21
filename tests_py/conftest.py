"""
Vault test fixtures for vault-certificate-deploy.

Requires `vault` binary on PATH (or VAULT_BIN env var pointing to it).
Spawns `vault server -dev` once per pytest session; each test gets
isolated KV/PKI mounts + approle so tests are independent of order.
"""

import grp
import os
import pwd
import shutil
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import hvac
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def vault_server(tmp_path_factory):
    """Run `vault server -dev` for the session. Yields {addr, token}."""
    bin_path = os.environ.get("VAULT_BIN") or shutil.which("vault")
    if not bin_path:
        pytest.skip("vault binary not found (set VAULT_BIN or put on PATH)")

    port = _free_port()
    addr = f"http://127.0.0.1:{port}"
    token = "root"
    log_file = tmp_path_factory.mktemp("vault") / "vault.log"

    proc = subprocess.Popen(
        [
            bin_path, "server", "-dev",
            "-dev-listen-address", f"127.0.0.1:{port}",
            "-dev-root-token-id", token,
        ],
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
    )

    client = hvac.Client(url=addr, token=token)
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            if client.sys.is_initialized():
                break
        except Exception:
            pass
        time.sleep(0.2)
    else:
        proc.terminate()
        pytest.fail(f"vault did not become ready; log: {log_file.read_text()}")

    yield {"addr": addr, "token": token}

    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="session")
def vault_client(vault_server):
    client = hvac.Client(url=vault_server["addr"], token=vault_server["token"])
    # Enable approle once at the default path the scripts hard-code; per-test
    # isolation is achieved with unique role names rather than unique mounts.
    try:
        client.sys.enable_auth_method(method_type="approle", path="approle")
    except hvac.exceptions.InvalidRequest:
        pass  # already enabled
    return client


@dataclass
class TestEnv:
    conf_file: Path
    storage_path: Path
    hooks_dir: Path
    kv_mount: str
    pki_mount: str
    role_name: str
    client: object
    tmp_path: Path


@pytest.fixture
def vault_test_env(vault_client, vault_server, tmp_path):
    """Per-test isolation: unique KV+PKI mounts and approle role + policy."""
    test_id = uuid.uuid4().hex[:8]
    kv_mount = f"cert_{test_id}"
    pki_mount = f"pki_{test_id}"
    policy_name = f"test_{test_id}"
    storage_path = tmp_path / "ssl"
    storage_path.mkdir()

    vault_client.sys.enable_secrets_engine(backend_type="kv", path=kv_mount)
    vault_client.sys.enable_secrets_engine(backend_type="pki", path=pki_mount)
    vault_client.write(
        f"{pki_mount}/root/generate/internal",
        common_name="Test CA",
        ttl="87000h",
    )
    vault_client.write(
        f"{pki_mount}/roles/test",
        ttl="30m",
        allow_subdomains=True,
        allowed_domains="test.intra",
    )

    vault_client.sys.create_or_update_policy(
        name=policy_name,
        policy=(
            f'path "/{kv_mount}/*" {{ capabilities = ["read","list"] }}\n'
            f'path "/{pki_mount}/*" {{ capabilities = ["read","list"] }}\n'
            f'path "/{pki_mount}/issue/*" {{ capabilities = ["create","update","read","list"] }}\n'
        ),
    )
    vault_client.write(f"auth/approle/role/{policy_name}", policies=policy_name)
    role_id = vault_client.read(
        f"auth/approle/role/{policy_name}/role-id"
    )["data"]["role_id"]
    secret_id = vault_client.write(
        f"auth/approle/role/{policy_name}/secret-id"
    )["data"]["secret_id"]

    # Default deploy user/group to whoever is running pytest. Without this,
    # the scripts fall back to root, and os.chown(..., 0, 0) fails as
    # non-root. Tests that specifically want root-only behaviour (e.g.
    # cert_owner=nobody) gate themselves with skip_if_not_root.
    me_user = pwd.getpwuid(os.getuid()).pw_name
    me_group = grp.getgrgid(os.getgid()).gr_name

    # Per-test post-hooks directory under tmp_path — no /etc/edrive write
    # access needed. Wired into the script via [hooks] post_hooks_dir.
    hooks_dir = tmp_path / "post-hooks.d"
    hooks_dir.mkdir()

    conf_file = tmp_path / "script.conf"
    conf_file.write_text(
        f"[vault]\n"
        f"address={vault_server['addr']}\n"
        f"verify_tls=no\n"
        f"mount_point={kv_mount}\n"
        f"deploy_user={me_user}\n"
        f"deploy_group={me_group}\n"
        f"\n"
        f"[approle]\n"
        f"role_id={role_id}\n"
        f"secret_id={secret_id}\n"
        f"\n"
        f"[storage]\n"
        f"path={storage_path}\n"
        f"\n"
        f"[hooks]\n"
        f"post_hooks_dir={hooks_dir}\n"
    )

    yield TestEnv(
        conf_file=conf_file,
        storage_path=storage_path,
        hooks_dir=hooks_dir,
        kv_mount=kv_mount,
        pki_mount=pki_mount,
        role_name=policy_name,
        client=vault_client,
        tmp_path=tmp_path,
    )

    try:
        vault_client.sys.disable_secrets_engine(path=kv_mount)
        vault_client.sys.disable_secrets_engine(path=pki_mount)
        vault_client.write(f"auth/approle/role/{policy_name}", method="DELETE")
        vault_client.sys.delete_policy(name=policy_name)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def make_cert():
    """Factory: generate a self-signed cert+key (PEM bytes)."""

    def _factory(days_valid: int = 365, common_name: str = "test") -> tuple[bytes, bytes]:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
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

    return _factory


@pytest.fixture
def seed_kv_cert(vault_test_env, make_cert):
    """Factory: write a freshly generated cert into the test's KV mount."""

    def _factory(name: str, days_valid: int = 365, common_name: str = "test"):
        crt, key = make_cert(days_valid=days_valid, common_name=common_name)
        vault_test_env.client.write(
            f"{vault_test_env.kv_mount}/{name}",
            crt=crt.decode(),
            key=key.decode(),
            bundle=crt.decode(),
        )
        return crt, key

    return _factory


@pytest.fixture
def seed_kv_raw(vault_test_env):
    """Factory: write arbitrary literal values into the test's KV mount.

    Useful for negative tests where we deliberately put bogus data into Vault.
    """

    def _factory(name: str, **kv):
        vault_test_env.client.write(f"{vault_test_env.kv_mount}/{name}", **kv)

    return _factory


# Resolve CLI scripts via the running interpreter's bin dir so the tests
# work regardless of whether the venv is activated.
_BIN_DIR = Path(sys.executable).parent
_DEPLOY_BIN = str(_BIN_DIR / "vault-certificate-deploy")
_ISSUE_BIN = str(_BIN_DIR / "vault-certificate-issue-deploy")


@pytest.fixture
def run_deploy(vault_test_env):
    """Factory: invoke vault-certificate-deploy CLI as subprocess."""

    def _runner(*extra_args):
        return subprocess.run(
            [
                _DEPLOY_BIN, "-d",
                "-c", str(vault_test_env.conf_file),
                *extra_args,
            ],
            capture_output=True, text=True,
        )

    return _runner


@pytest.fixture
def run_issue(vault_test_env):
    """Factory: invoke vault-certificate-issue-deploy CLI as subprocess."""

    def _runner(*extra_args):
        return subprocess.run(
            [
                _ISSUE_BIN, "-d",
                "--cert-role", "test",
                "--vault-pki", vault_test_env.pki_mount,
                "-c", str(vault_test_env.conf_file),
                *extra_args,
            ],
            capture_output=True, text=True,
        )

    return _runner


@pytest.fixture
def write_cert_list(vault_test_env):
    """Factory: write a cert-list file in tmp_path and return its path."""

    def _factory(*lines, name: str = "certs.conf") -> Path:
        path = vault_test_env.tmp_path / name
        path.write_text("\n".join(lines) + "\n")
        return path

    return _factory
