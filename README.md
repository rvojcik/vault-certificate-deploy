# vault-cert-deploy

![pipeline](https://gitlab.com/rvojcik/vault-certificate-deploy/badges/master/pipeline.svg)

Deploy SSL certificates from HashiCorp's Vault secret server
Script is able to deploy certificates from KV store of Vault
or when you use issue version of script it use PKI secret storage.

As auth method is used [Approle](https://www.vaultproject.io/docs/auth/approle.html "Vault Approle Doc"), you need role and secret id
deployed to server from different systems/locations. More
about this in usecase section.

On the first look, it may be little bit strange combination of 
config file and cli options. You can combine them in different 
ways to support various types of deployments to meet the basic
security concepts.

## Why do I need Vault Server ?

We are using Let's Encrypt for almost all of our SSL/TLS certificates.
We also have complex infrastructure so we have to retrieve 
certificates in central place and then we distribute them into 
datacenters, clouds or any other applications.

## How deploy work ?

It deploy certificates to specified directory and create
two directories `certs` and `private`.

* certs has mode 0644
* private keys has mode 0640
* it deploys all secret content from vault, keys as files with suitable extension <secretname>.<secretKey>

## Installation

### Python PyPI
```
pip install vault-certificate-deploy
```

### Manual
Manual installation

```
git clone https://github.com/rvojcik/vault-certificate-deploy
cd vault-certificate-deploy
sudo python ./setup.py install 
```

In the end 
```
vault-certificate-deploy --help
```

## Example configuration
Can be found in `config.example`. 

Role and Secret id can be passed from script arguments.
You could combine `-n` and `--cert-list` parameters.

In `vault` section of configuration it is possible to 
set `mount_point` of secret in Vault. 
By default it is `cert`.
You could also change this option in arguments

## Per-certificate options in cert-list file

Each line in your cert-list file can carry per-certificate overrides using
semicolon-delimited `key=value` pairs as the last field. Settings here take
precedence over the global CLI flags and config defaults.

For the deploy script — line format: `<cert_name> [options]`. Available options:
* `cert_owner`, `cert_group` — file owner / group (overrides `deploy_user` / `deploy_group`)
* `cert_perms` — octal permissions for cert files (default `0644`; key files are always `0640`)
* `cert_copypath` — additional flat directory to copy all cert files into

See `cert_list.example` for a full reference.

For the issue script — line format: `<cert_name> [pki_mount] [pki_policy] [options]`.
Above options plus:
* `cert_ttl` — TTL when issuing the certificate (overrides `--cert-ttl`)
* `cert_renew_min_ttl` — renewal threshold in seconds (overrides `--cert-min-ttl`)
* Any Vault PKI parameter — `alt_names`, `ip_sans`, `uri_sans`, `other_sans`, `exclude_cn_from_sans`, ...

See `cert_list_issue.example` for a full reference.

Examples:
```
server1.domain.intra cert_owner=nginx;cert_group=nginx;cert_perms=640
server2.domain.intra cert_copypath=/etc/haproxy/certs/
server3.domain.intra pki default alt_names=api.domain.intra;cert_ttl=2592000
```

# Vault Configuration

Script uses [Approle](https://www.vaultproject.io/docs/auth/approle.html "Vault Approle Doc") auth.

First enable AppRole auth if it's not
```
vault auth enable approle
```

You have to create your policy first.
Use Vault [documentation](https://www.vaultproject.io/docs/concepts/policies.html) around policies and then continue here.

Example policy with basic medium security can be
```
# Cert Deploy Policy
# Give ability to
# - read all certificates
# - don't permit list certificates
#
path "/certs/*" {
  capabilities = ["read"]
}

```

Configure your role
```
vault write auth/approle/role/my-role \
secret_id_ttl=0 \
token_num_uses=0 \
token_ttl=20m \
token_max_ttl=30m \
policies="my-policy,default"
```

Retrieve your approle ID
```
vault read auth/approle/role/my-role/role-id
```

Get secret ID (onetime operation)
```
vault write -f auth/approle/role/my-role/secret-id
```

# Use Cases
It is important to don't have role-id and secret-id together
in one repository or configuration management.

## Puppet
I deploy my servers with installer which create file `/etc/vault_role_id`
which contain `role-id` of the approle.

Then I have Puppet Configuration management which deploy this system with 
all files and `secret-id` in configuration file (`/etc/vault-deploy/config.conf`). 

Puppet create also file with certs/secret names `/etc/ssl-deploy-certs.conf`

then you can run deploy like this:
```
vault-certificate-deploy.py -c /etc/vault-deploy/config.conf \
  --cert-list /etc/ssl-deploy-certs.conf \
  --role-id $(cat /etc/vault_role_id)
```

### Why  ?
I store Puppet configuration in Git, and therefore I have not 
role-id and secret-id together in my repository.
I choose to deploy `secret-id` with puppet because when need to 
rotate secret-id it is automaticly deployed by puppet to infrastructure.

## What is issue version of the script ?
Issue version of the command or script uses different Secret Storage
Engine. It uses [PKI](https://www.vaultproject.io/api/secret/pki/index.html) which gives you ability to create
your own CA or Intermediate CA. Vault handle both certs generation and issuing. 

You have to specify PKI mount point with `--vault-pki` option.
This pki mount_point is used as subdirectory of storage path in your
config file. In this subdirectory we create same structure `certs` and `private`
like in other version of the script.

### What is difference in function ?
Issue command check if certificates you define exists, and it check their expiration time
defined by `--cert-min-ttl` option. 

It basicaly means it generates and issue certificates for you, if they not exist, or if they are 
close to expire. It is great automation capability in combination with Configuration
Management systems. You don't have to take care of the certificates anymore.

If certificates you define exists and are valid script just do nothing.

### Examples
Create certificate server1.domin.intra on PKI mounted in pki mount point of vault.
If you want to issue new certificate, you have to issue it against some role. In 
our case this role is `test`.

More information about [PKI roles in documentation](https://www.vaultproject.io/docs/secrets/pki/index.html).
```
vault-certificate-issue-deploy --vault-pki pki -n server1.domain.intra --cert-role test
```

If we need some subject alternative name you can define it as `--cert-extra-options`
```
vault-certificate-issue-deploy --vault-pki pki -n server1.domain.intra --cert-role test --cert-extra-options "alt_names=console.domain.intra,console1.domain.intra,admin.domain.intra"
```
Result of this can be something like this
```
 X509v3 Subject Alternative Name: 
     DNS:console.domain.intra, DNS:console1.domain.intra, DNS:admin.domain.intra
```

# Post-deploy hooks

Both scripts can run executable scripts from a hooks directory after a deploy
or issue run, but **only when at least one certificate file was actually
written or changed on disk**. This makes the scripts safe to run on a cron
schedule — services like nginx or haproxy only get reloaded when there's a
real reason.

The hook directory is configurable in the config file:
```
[hooks]
post_hooks_dir=/etc/edrive/certificate-hooks.d
```

If the `[hooks]` section is omitted, each script falls back to its
historical built-in default:
* `/etc/edrive/vault-certificate-deploy/post-hooks.d/` — for the deploy script
* `/etc/edrive/vault-certificate-deploy/post-issue-hooks.d/` — for the issue script

Drop any executable file into the hook directory (e.g. a shell script that
calls `systemctl reload nginx`). Hooks are executed in the order returned by
the filesystem. A non-zero exit from a hook is counted as an error in the
overall exit code but does not stop subsequent hooks from running.

Example hook script:
```bash
#!/bin/bash
systemctl reload nginx
```

# Security Best Practices
* Never store your role-id and secret-id in your repository together
* Deploy secret-id in way it's quick and easy for you to rotate/change
* In production always use `verify_tls=yes`
* when deploy secret-id and role-id in files/config, always set correct permissions (eg. `0400`, `0600`)
* in vault set policy to your approle only for `read` capability, it's enough
* for highest security set individual approle for every server and set individual policy for every server and certificate

# Development & Testing

Tests live in `tests_py/` and run with pytest. The suite has two layers:

* **Unit tests** for the shared certificate helpers — no Vault required, run in
  under a second:
  ```
  pytest tests_py/test_cert_ops_unit.py
  ```

* **Integration tests** that spawn `vault server -dev` and exercise the real
  CLI scripts:
  ```
  pytest tests_py/
  ```
  Requires the `vault` binary on `PATH` (or set `VAULT_BIN` env var). Each
  test gets an isolated KV+PKI mount, so test order doesn't matter and tests
  can run in parallel with `pytest -n auto` after installing `pytest-xdist`.

Two tests use `chown` to a non-current user and are automatically skipped
unless pytest runs as root. The hooks tests write into `/etc/edrive/...` and
need the same privilege.

The CI pipeline (`.gitlab-ci.yml`) runs the full suite against Python 3.9 and
3.11 on every merge request. Local Docker-Compose-based runs are wired up via
`dev/docker-compose.yaml` and `dev/run-tests.sh`.

