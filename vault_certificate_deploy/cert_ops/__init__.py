"""
Shared certificate operations used by both deploy scripts:
directory creation, config validation, cert validation/check, post-hook runner.
"""

import calendar
import os
import subprocess
import time

import OpenSSL

from .. import base


# Required config sections and options
config_map = {
    "vault": ["address", "verify_tls"],
    "storage": ["path"],
}


def validate_configuration(parsed_config: base.ConfigParse) -> None:
    """Validate configuration for required options and format"""

    config_result_test = True
    # Test sections
    for section in ["vault", "approle", "storage"]:
        if not parsed_config.parser.has_section(section):
            base.perr(f"No section {section} in configuration file")
            config_result_test = False

    # Test options
    for section in config_map.keys():
        for option in config_map[section]:
            if not parsed_config.parser.has_option(section, option):
                base.perr(f"No options {option} in section {section}")
                config_result_test = False

    if not config_result_test:
        base.eexit(1, "Configuration errors")


def create_directory(
    path: str,
    perms: int,
    user_id: int,
    group_id: int,
    exit_on_error: bool = True,
    keep_previous_ownership: bool = False,
    debug: bool = False,
) -> bool:
    """Create directory with permissions and ownership"""

    if not os.path.isdir(path):
        try:
            os.makedirs(path, perms)
            base.pdeb(f"CHOWN {path} -> {user_id}:{group_id}", debug)
            os.chown(path, user_id, group_id)
            os.chmod(path, perms)
        except Exception as _:
            base.perr(f"Unable to create directory {path}")
            if exit_on_error:
                base.eexit(1, "Error occured while creating directory")
            else:
                return False
    elif not keep_previous_ownership:
        base.pdeb(f"CHOWN {path} -> {user_id}:{group_id}", debug)
        os.chown(path, user_id, group_id)
        os.chmod(path, perms)

    return True


def certificate_validate(cert_t: tuple, cert_min_ttl: int = 345600) -> bool:
    """Validate freshly-fetched certificate tuple from Vault.

    Warns when the cert's remaining TTL is below cert_min_ttl. For the
    issue script this indicates the Vault role's max_ttl is capping
    cert_ttl and the script will renew on every run; for the deploy
    script it just means the cert pulled from KV is about to expire.
    """

    mount = cert_t[0].get("pki_mount_name", "n/a")

    try:
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM, cert_t[1]["data"]["crt"]
        )
    except OpenSSL.crypto.Error as e:
        base.perr(
            f"Certificate {cert_t[0]['name']}:{mount} not valid format: {str(e)}"
        )
        return False

    try:
        private_key = OpenSSL.crypto.load_privatekey(
            OpenSSL.crypto.FILETYPE_PEM, cert_t[1]["data"]["key"]
        )
        private_key.check()
    except TypeError as e:
        base.perr(f"Private key in bad format for {cert_t[0]['name']}: {str(e)}")
        return False
    except OpenSSL.crypto.Error as e:
        base.perr(f"Private key inconsistent for {cert_t[0]['name']}: {str(e)}")
        return False

    seconds_expire = (
        calendar.timegm(time.strptime(x509.get_notAfter().decode(), "%Y%m%d%H%M%SZ"))
        - time.time()
    )
    if seconds_expire < cert_min_ttl:
        base.pwrn(
            f"Certificate {cert_t[0]['name']} TTL ({seconds_expire}s) "
            f"is below threshold ({cert_min_ttl}s)"
        )

    return True


def certificate_check(
    cert_name: str,
    cert_file: str,
    cert_priv_file: str,
    cert_min_ttl: int,
    debug: bool = False,
) -> bool:
    """Check validity and existence of the certificate on disk"""

    if not os.path.isfile(cert_file):
        return False

    if not os.path.isfile(cert_priv_file):
        return False

    with open(cert_file, "r") as f:
        try:
            x509 = OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM, f.read()
            )
        except OpenSSL.crypto.Error as e:
            base.perr(f"Certificate {cert_name} not valid format: {e}")
            return False

    seconds_expire = (
        calendar.timegm(time.strptime(x509.get_notAfter().decode(), "%Y%m%d%H%M%SZ"))
        - time.time()
    )
    seconds_min_ttl = cert_min_ttl

    if seconds_expire < seconds_min_ttl:
        base.pwrn(
            f"Certificate {cert_name} is about to expire ({seconds_expire} < {seconds_min_ttl} seconds)"
        )
        return False
    else:
        base.pdeb(
            f"Certificate {cert_name} is ok. TTL to expire is {seconds_expire} seconds",
            debug,
        )
        return True


def run_post_hooks(post_hooks_dir: str, debug: bool) -> int:
    """Run post hooks and return number of errors"""

    errors_count = 0

    base.pdeb("Trying to run script from hooks directory: " + post_hooks_dir, debug)
    if os.path.exists(post_hooks_dir) and os.path.isdir(post_hooks_dir):
        if not os.listdir(post_hooks_dir):
            base.pdeb("Hooks directory " + post_hooks_dir + " is empty", debug)
        else:
            for hook in os.listdir(post_hooks_dir):
                hook_fp = post_hooks_dir + "/" + hook
                base.pdeb("Running post hook: " + hook, debug)
                hook_result = subprocess.run(
                    hook_fp, shell=True, text=True, capture_output=True
                )
                if hook_result.returncode > 0:
                    base.pdeb("There was error during the hook execution", debug)
                    if hook_result.stderr:
                        base.pdeb("STDERR output:", debug)
                        base.pdeb(hook_result.stderr, debug)
                    errors_count += 1
    else:
        base.pdeb("Hooks directory " + post_hooks_dir + " doesn't exist", debug)

    return errors_count
