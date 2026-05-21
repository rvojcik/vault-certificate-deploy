"""
Integration tests for post-hooks behaviour (pytest port of 30-hooks.sh).

The hook directory is now driven by the [hooks] post_hooks_dir option in
script.conf (set by the vault_test_env fixture to a per-test tmp path), so
these tests run as any user — no /etc/ write access required.
"""


def _install_marker_hook(env, marker_name: str = "hook-fired"):
    """Drop a touch-the-marker hook into the env's hooks_dir."""
    marker = env.tmp_path / marker_name
    hook = env.hooks_dir / "01-touch.sh"
    hook.write_text(f"#!/bin/bash\ntouch {marker}\n")
    hook.chmod(0o755)
    return marker


def test_deploy_hook_fires_on_change_and_quiet_on_noop(
    vault_test_env, seed_kv_cert, write_cert_list, run_deploy
):
    seed_kv_cert("test-cert")
    cert_list = write_cert_list("test-cert")
    marker = _install_marker_hook(vault_test_env)

    # First run: writes cert -> hook fires
    r = run_deploy("--cert-list", str(cert_list))
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert marker.exists(), "hook did not fire after fresh write"

    # Second run: identical content -> change-detection skips -> no hook
    marker.unlink()
    r = run_deploy("--cert-list", str(cert_list))
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert not marker.exists(), (
        "hook fired on no-op run — change-detection regressed"
    )


def test_issue_hook_fires_on_renewal_and_quiet_on_noop(
    vault_test_env, write_cert_list, run_issue
):
    env = vault_test_env
    cert_list = write_cert_list(f"test1.test.intra {env.pki_mount} test")
    marker = _install_marker_hook(env)

    # Force reissue: PKI test role caps TTL at 30m, well below 90000s threshold
    r = run_issue("--cert-list", str(cert_list), "--cert-ttl", "86700", "--cert-min-ttl", "90000")
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert marker.exists(), "hook did not fire after renewal"

    # Cert now exists with TTL ~30m; threshold 1s -> no renewal -> no hook
    marker.unlink()
    r = run_issue("--cert-list", str(cert_list), "--cert-ttl", "86700", "--cert-min-ttl", "1")
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    assert not marker.exists(), "hook fired on no-op run"
