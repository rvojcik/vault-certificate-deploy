#!/bin/bash

cat <<EOF
==================================================
DEPLOY 2
--------
Deploy 1 invalid certificate with ignore-ssl-check
This step should remove test-cert2 and update
test-cert1 with new content
==================================================
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

# Test second deploy
./vault kv delete cert/test-cert1
./vault kv put cert/test-cert1 key=privatekey2 ica=interca2 crt=certificate2 bundle=bundle2
./vault kv get cert/test-cert1

$script -c ./script.conf --cert-list deploy2.conf --ignore-ssl-check
tree $cert_destination
grep privatekey2 $cert_destination/private/test-cert1/test-cert1.key
grep interca2 $cert_destination/certs/test-cert1/test-cert1.ica
grep certificate2 $cert_destination/certs/test-cert1/test-cert1.crt
grep bundle2 $cert_destination/private/test-cert1/test-cert1.bundlekey
grep privatekey2 $cert_destination/private/test-cert1/test-cert1.bundlekey

set +e

if [[ -d $cert_destination/certs/test-cert2 ]] ; then
    echo "Certificate not removed, clean function not work"
    exit 1
fi 
if [[ -d $cert_destination/private/test-cert2 ]] ; then
    echo "Certificate not removed, clean function not work"
    exit 1
fi 
