#!/bin/bash

cat <<EOF
=================
PREPARING SECRETS
=================
EOF

if [[ -f ./vault.env ]] ; then
  . ./vault.env
else
  echo "Unable to find vault.env file from previous step"
  exit 1
fi

# Exit when something wrong
set -e

# Basic dir
mkdir -p $cert_destination

echo "Prepare cert storage in vault"
./vault secrets enable -path cert kv
./vault kv put cert/test-cert1 key="$(cat tests/certs/cert1.key)" crt="$(cat tests/certs/cert1.crt)"
./vault kv get cert/test-cert1
./vault kv put cert/test-cert2 key="$(cat tests/certs/cert2.key)" crt="$(cat tests/certs/cert2.crt)"
./vault kv get cert/test-cert2
./vault kv put cert/invalid-cert key="asdgasdfasdf" crt="asdfasdfasdf"
./vault kv get cert/invalid-cert

echo "Generate config for project"
cat > script.conf <<EOF
[vault]
address=$VAULT_ADDR
verify_tls=no

[approle]
role_id=$role_id
secret_id=$secret_id

[storage]
path=$cert_destination
EOF

echo "Prepair deploy config1"
cat > deploy1.conf <<EOF
test-cert1
test-cert2
EOF

echo "Prepair deploy config2"
cat > deploy2.conf <<EOF
test-cert1
EOF

echo "Prepair deploy config3"
cat > deploy3.conf <<EOF
invalid-cert
EOF

echo "Prepair client deploy"
cat > client_cert.conf << EOF
test1.test.intra
test2.test.intra
EOF
