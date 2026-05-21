"""
Integration tests for vault-certificate-issue-deploy.

Ports the shell tests 20-issue1, 21-renew, 22-issue2, 23-clean.
Each test gets its own Vault PKI mount via vault_test_env; the test
role caps cert TTL at 30 minutes so renewal can be triggered with a
small --cert-min-ttl threshold.
"""

import grp
import os
import pwd
from pathlib import Path

import pytest


def _stat(path: Path):
    st = path.stat()
    return {
        "user": pwd.getpwuid(st.st_uid).pw_name,
        "group": grp.getgrgid(st.st_gid).gr_name,
        "mode": st.st_mode & 0o777,
    }


def _cert_dir(env, name: str) -> Path:
    return env.storage_path / env.pki_mount / "certs" / name


def _priv_dir(env, name: str) -> Path:
    return env.storage_path / env.pki_mount / "private" / name


# ---------------------------------------------------------------------------
# 20-issue1.sh — issue 2 client certificates
# ---------------------------------------------------------------------------


def test_issue_two_client_certs(vault_test_env, write_cert_list, run_issue):
    env = vault_test_env
    cert_list = write_cert_list(
        f"test1.test.intra {env.pki_mount} test",
        f"test2.test.intra {env.pki_mount} test",
    )

    r = run_issue("--cert-list", str(cert_list), "--cert-ttl", "86700", "--cert-min-ttl", "7200")
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"

    for name in ("test1.test.intra", "test2.test.intra"):
        crt = _cert_dir(env, name) / f"{name}.crt"
        key = _priv_dir(env, name) / f"{name}.key"
        ica = _cert_dir(env, name) / f"{name}.ica"
        assert crt.read_text().startswith("-----BEGIN CERTIFICATE-----")
        assert "PRIVATE KEY" in key.read_text()
        assert ica.read_text().startswith("-----BEGIN CERTIFICATE-----")


# ---------------------------------------------------------------------------
# 21-renew.sh — high --cert-min-ttl forces renewal
# ---------------------------------------------------------------------------


def test_issue_renews_when_below_min_ttl(vault_test_env, write_cert_list, run_issue):
    env = vault_test_env
    cert_list = write_cert_list(
        f"test1.test.intra {env.pki_mount} test",
        f"test2.test.intra {env.pki_mount} test",
    )

    # Initial issue
    assert run_issue("--cert-list", str(cert_list), "--cert-ttl", "86700", "--cert-min-ttl", "7200").returncode == 0
    before = {
        name: (_cert_dir(env, name) / f"{name}.crt").read_text()
        for name in ("test1.test.intra", "test2.test.intra")
    }

    # Threshold above the role's 30-minute cap -> both certs are below
    # threshold -> both must be reissued, contents must differ.
    r = run_issue("--cert-list", str(cert_list), "--cert-ttl", "86700", "--cert-min-ttl", "90000")
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"

    after = {
        name: (_cert_dir(env, name) / f"{name}.crt").read_text()
        for name in ("test1.test.intra", "test2.test.intra")
    }
    for name in before:
        assert before[name] != after[name], f"{name} should have been reissued"


# ---------------------------------------------------------------------------
# 22-issue2.sh — per-cert ownership, permissions, copypath
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.geteuid() != 0, reason="chown to other users needs root")
def test_issue_per_cert_owner_perms_and_copypath(
    vault_test_env, write_cert_list, run_issue, tmp_path
):
    try:
        pwd.getpwnam("nobody")
    except KeyError:
        pytest.skip("user 'nobody' not present on the test runner")

    env = vault_test_env
    copypath = tmp_path / "copypath"
    me_user = pwd.getpwuid(os.getuid()).pw_name
    me_group = grp.getgrgid(os.getgid()).gr_name

    cert_list = write_cert_list(
        f"test4.test.intra {env.pki_mount} test "
        f"cert_owner=nobody;cert_perms=664;cert_copypath={copypath}",
        f"test3.test.intra {env.pki_mount} test "
        f"cert_owner={me_user};cert_group={me_group};cert_perms=400;cert_copypath={copypath}",
    )

    r = run_issue("--cert-list", str(cert_list), "--cert-ttl", "86700", "--cert-min-ttl", "7200")
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"

    # ---- test3: current user, perms 400 ----
    crt3 = _cert_dir(env, "test3.test.intra") / "test3.test.intra.crt"
    key3 = _priv_dir(env, "test3.test.intra") / "test3.test.intra.key"
    assert _stat(crt3) == {"user": me_user, "group": me_group, "mode": 0o400}
    assert _stat(key3)["mode"] == 0o640

    cp3_crt = copypath / "test3.test.intra.crt"
    cp3_key = copypath / "test3.test.intra.key"
    assert cp3_crt.exists() and cp3_key.exists()
    assert _stat(cp3_crt)["mode"] == 0o400
    assert _stat(cp3_key)["mode"] == 0o640

    # ---- test4: nobody owner, perms 664 ----
    crt4 = _cert_dir(env, "test4.test.intra") / "test4.test.intra.crt"
    key4 = _priv_dir(env, "test4.test.intra") / "test4.test.intra.key"
    assert _stat(crt4)["user"] == "nobody"
    assert _stat(crt4)["mode"] == 0o664
    assert _stat(key4)["mode"] == 0o640

    cp4_crt = copypath / "test4.test.intra.crt"
    assert cp4_crt.exists()
    assert _stat(cp4_crt)["user"] == "nobody"
    assert _stat(cp4_crt)["mode"] == 0o664


# ---------------------------------------------------------------------------
# 23-clean.sh — certs not in the list are removed
# ---------------------------------------------------------------------------


def test_issue_cleans_certs_no_longer_in_list(vault_test_env, write_cert_list, run_issue):
    env = vault_test_env

    full_list = write_cert_list(
        f"test1.test.intra {env.pki_mount} test",
        f"test2.test.intra {env.pki_mount} test",
        name="full.conf",
    )
    assert run_issue("--cert-list", str(full_list), "--cert-ttl", "86700", "--cert-min-ttl", "7200").returncode == 0
    assert _cert_dir(env, "test1.test.intra").exists()
    assert _cert_dir(env, "test2.test.intra").exists()

    short_list = write_cert_list(
        f"test1.test.intra {env.pki_mount} test",
        name="short.conf",
    )
    # Use the renewal-forcing threshold from the original test so the run
    # exercises the same code path; only matters that the script gets to
    # clean_certificates at the end.
    r = run_issue("--cert-list", str(short_list), "--cert-ttl", "86700", "--cert-min-ttl", "90000")
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"

    assert _cert_dir(env, "test1.test.intra").exists()
    assert not _cert_dir(env, "test2.test.intra").exists()
    assert not _priv_dir(env, "test2.test.intra").exists()

    remaining_crts = list((env.storage_path / env.pki_mount).rglob("*.crt"))
    assert len(remaining_crts) == 1, f"expected 1 cert, got {remaining_crts}"
