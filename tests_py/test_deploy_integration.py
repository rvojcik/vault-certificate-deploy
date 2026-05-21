"""
Integration tests for vault-certificate-deploy.

Ports the shell tests 10-deploy1, 11-deploy2, 12-deploy3-fail,
13-deploy4-noexist, 14-deploy5. Each test gets its own Vault KV mount
via the vault_test_env fixture, so they are order-independent.
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


# ---------------------------------------------------------------------------
# 10-deploy1.sh — deploy 2 valid certificates
# ---------------------------------------------------------------------------


def test_deploy_two_valid_certs_writes_all_files(
    vault_test_env, seed_kv_cert, write_cert_list, run_deploy
):
    crt1, key1 = seed_kv_cert("test-cert1")
    crt2, key2 = seed_kv_cert("test-cert2")
    cert_list = write_cert_list("test-cert1", "test-cert2")

    r = run_deploy("--cert-list", str(cert_list))
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"

    storage = vault_test_env.storage_path
    for name in ("test-cert1", "test-cert2"):
        crt = storage / "certs" / name / f"{name}.crt"
        key = storage / "private" / name / f"{name}.key"
        bundle = storage / "certs" / name / f"{name}.bundle"
        bundlekey = storage / "private" / name / f"{name}.bundlekey"

        assert crt.read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")
        assert key.read_text().find("PRIVATE KEY") != -1
        assert bundle.exists()
        assert "CERTIFICATE" in bundlekey.read_text()
        assert "PRIVATE KEY" in bundlekey.read_text()


# ---------------------------------------------------------------------------
# 11-deploy2.sh — update content + clean removed certs
# ---------------------------------------------------------------------------


def test_deploy_updates_content_and_cleans_removed_certs(
    vault_test_env, seed_kv_cert, seed_kv_raw, write_cert_list, run_deploy
):
    # First: deploy both certs normally
    seed_kv_cert("test-cert1")
    seed_kv_cert("test-cert2")
    list_both = write_cert_list("test-cert1", "test-cert2", name="both.conf")
    assert run_deploy("--cert-list", str(list_both)).returncode == 0

    # Now replace test-cert1 in Vault with literal strings (not PEM) and
    # rerun with --ignore-ssl-check; deploy2 lists only test-cert1, so
    # test-cert2 should be cleaned from disk.
    seed_kv_raw(
        "test-cert1",
        key="privatekey2",
        ica="interca2",
        crt="certificate2",
        bundle="bundle2",
    )
    list_one = write_cert_list("test-cert1", name="one.conf")
    r = run_deploy("--cert-list", str(list_one), "--ignore-ssl-check")
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"

    storage = vault_test_env.storage_path
    assert (storage / "private" / "test-cert1" / "test-cert1.key").read_text() == "privatekey2"
    assert (storage / "certs" / "test-cert1" / "test-cert1.crt").read_text() == "certificate2"
    assert (storage / "certs" / "test-cert1" / "test-cert1.ica").read_text() == "interca2"

    # test-cert2 directories should have been removed by clean_certificates
    assert not (storage / "certs" / "test-cert2").exists()
    assert not (storage / "private" / "test-cert2").exists()


# ---------------------------------------------------------------------------
# 12-deploy3-fail.sh — deploy fails on cert with invalid PEM
# ---------------------------------------------------------------------------


def test_deploy_fails_on_invalid_pem(
    vault_test_env, seed_kv_raw, write_cert_list, run_deploy
):
    seed_kv_raw("invalid-cert", key="asdgasdfasdf", crt="asdfasdfasdf")
    cert_list = write_cert_list("invalid-cert")

    r = run_deploy("--cert-list", str(cert_list))
    assert r.returncode != 0, "deploy should fail on invalid PEM"

    # No cert files should have been left on disk
    assert list(vault_test_env.storage_path.rglob("*.crt")) == []


# ---------------------------------------------------------------------------
# 13-deploy4-noexist.sh — deploy fails on cert that doesn't exist in Vault
# ---------------------------------------------------------------------------


def test_deploy_fails_on_nonexistent_cert(vault_test_env, write_cert_list, run_deploy):
    cert_list = write_cert_list("_cert.that.not-exists")

    r = run_deploy("--cert-list", str(cert_list))
    assert r.returncode != 0, "deploy should fail on missing Vault secret"
    assert list(vault_test_env.storage_path.rglob("*.crt")) == []


# ---------------------------------------------------------------------------
# 14-deploy5.sh — per-cert ownership, permissions, copypath
# ---------------------------------------------------------------------------


def _assert_user_exists(name: str):
    try:
        pwd.getpwnam(name)
    except KeyError:
        pytest.skip(f"user {name!r} not present on the test runner")


@pytest.mark.skipif(os.geteuid() != 0, reason="chown to other users needs root")
def test_deploy_per_cert_owner_perms_and_copypath(
    vault_test_env, seed_kv_cert, write_cert_list, run_deploy, tmp_path
):
    _assert_user_exists("nobody")

    seed_kv_cert("test-cert3")
    seed_kv_cert("test-cert4")
    copypath = tmp_path / "copypath"
    me_user = pwd.getpwuid(os.getuid()).pw_name
    me_group = grp.getgrgid(os.getgid()).gr_name

    cert_list = write_cert_list(
        f"test-cert4 cert_owner=nobody;cert_perms=664;cert_copypath={copypath}",
        f"test-cert3 cert_owner={me_user};cert_group={me_group};cert_perms=400;cert_copypath={copypath}",
    )

    r = run_deploy("--cert-list", str(cert_list))
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"

    storage = vault_test_env.storage_path

    # ---- test-cert3: current user, perms 400 ----
    cert3_crt = storage / "certs" / "test-cert3" / "test-cert3.crt"
    cert3_key = storage / "private" / "test-cert3" / "test-cert3.key"
    assert _stat(cert3_crt) == {"user": me_user, "group": me_group, "mode": 0o400}
    assert _stat(cert3_key)["mode"] == 0o640  # key perms are always 0640

    cp3_crt = copypath / "test-cert3.crt"
    cp3_key = copypath / "test-cert3.key"
    assert cp3_crt.exists() and cp3_key.exists()
    assert _stat(cp3_crt)["mode"] == 0o400
    assert _stat(cp3_key)["mode"] == 0o640

    # ---- test-cert4: nobody owner, perms 664 ----
    cert4_crt = storage / "certs" / "test-cert4" / "test-cert4.crt"
    cert4_key = storage / "private" / "test-cert4" / "test-cert4.key"
    assert _stat(cert4_crt)["user"] == "nobody"
    assert _stat(cert4_crt)["mode"] == 0o664
    assert _stat(cert4_key)["mode"] == 0o640

    cp4_crt = copypath / "test-cert4.crt"
    assert cp4_crt.exists()
    assert _stat(cp4_crt)["user"] == "nobody"
    assert _stat(cp4_crt)["mode"] == 0o664

    # Copypath directory itself: owner is whoever created it first (nobody, the
    # first entry in the cert list), group is the running user's group.
    assert _stat(copypath)["user"] == "nobody"
    assert _stat(copypath)["group"] == me_group
