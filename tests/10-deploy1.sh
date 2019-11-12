#!/bin/bash

cat <<EOF
===========================
DEPLOY 1
--------
Deploy 2 valid certificates
===========================
EOF


if [[ -f ./vault.env ]] ; then
  . ./vault.env
else
  echo "Unable to find vault.env file from previous step"
  exit 1
fi

# Exit when something wrong
set -e

# Test first deploy
$script -c ./script.conf --cert-list deploy1.conf 
tree $cert_destination
grep -E 'BEGIN.*PRIVATE' $cert_destination/private/test-cert1/test-cert1.key
grep -E 'BEGIN CERTIFICATE' $cert_destination/certs/test-cert1/test-cert1.crt
grep -E 'BEGIN.*PRIVATE' $cert_destination/private/test-cert2/test-cert2.key
grep -E 'BEGIN CERTIFICATE' $cert_destination/certs/test-cert2/test-cert2.crt
