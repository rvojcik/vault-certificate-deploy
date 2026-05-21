#!/bin/bash

set -e

echo "Entering directory $1"
cd "$1/"

# System packages required by the test environment
apt-get update
apt-get install -y $(cat tests_py/system-requirements.txt)

# Vault dev binary (used by the session-scoped vault_server fixture)
vault_version=1.8.5
wget -q "https://releases.hashicorp.com/vault/${vault_version}/vault_${vault_version}_linux_amd64.zip" -O /tmp/vault.zip
unzip -o /tmp/vault.zip -d /usr/local/bin/
chmod +x /usr/local/bin/vault

# Project + test dependencies (hvac comes from the project's requirements.txt
# so versions stay aligned with what the scripts ship against)
pip install -r requirements.txt
pip install -r tests_py/requirements-dev.txt
python setup.py install

# Run the pytest suite
exec pytest tests_py/ -v
