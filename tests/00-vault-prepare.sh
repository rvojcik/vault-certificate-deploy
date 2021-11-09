#!/bin/bash

export VAULT_ADDR=http://localhost:8200
vault_output_file=./vault.log
vault_download_addr="https://releases.hashicorp.com/vault"
vault_latest_rel=vault_1.8.5
vault_version=${vault_latest_rel/#vault_/}
cert_destination=/etc/edrive/ssl
script="vault-certificate-deploy -d --vault-mount cert"
script2="vault-certificate-issue-deploy -d --cert-role test --vault-pki pki"

cat <<EOF
======================================
PREPARING VAULT SERVER
----------------------
Preparing basic vault installation and
basic configuration
======================================
EOF

# Exit when something wrong
set -e
# Basic dir
mkdir -p $cert_destination

wget -q $vault_download_addr/$vault_version/${vault_latest_rel}_linux_amd64.zip -O vault.zip
unzip ./vault.zip

# Policy file
cat > policy.hcl <<EOF
path "/cert/*" {
  capabilities = ["read", "list"]
}

path "/pki/*" {
  capabilities = ["read", "list"]
}
path "/pki/issue/*" {
  capabilities = ["create", "update", "read", "list"]
}
EOF

echo "Running vault"
./vault server -dev > $vault_output_file 2> /dev/null &
sleep 4
vault_token=$(sed -n 's/^Root Token: \(.*\)/\1/p' $vault_output_file)

echo "Login to vault"
echo "$vault_token" | ./vault login -

echo "Prepare approle"
./vault auth enable -path approle approle
./vault policy write test ./policy.hcl
./vault write auth/approle/role/test policies=test
role_id=$(./vault read auth/approle/role/test/role-id | sed -n 's/^role_id \+\(.*\)/\1/p')
secret_id=$(./vault write -f auth/approle/role/test/secret-id | sed -n 's/^secret_id \+\(.*\)/\1/p')

echo "Enable PKI"
./vault secrets enable -path pki pki
./vault secrets tune -max-lease-ttl=8760h pki
./vault write pki/root/generate/internal common_name="Testing CA" ttl=87000h
./vault write pki/roles/test ttl=30m allow_subdomains=true allowed_domains=test.intra

echo "Vault is running"
echo "Generating config"
cat > vault.env <<EOF
export VAULT_ADDR=$VAULT_ADDR
export role_id=$role_id
export secret_id=$secret_id
export vault_token=$vault_token
export cert_destination=$cert_destination
export script="$script"
export script2="$script2"
EOF

