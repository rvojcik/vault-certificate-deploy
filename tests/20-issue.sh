#!/bin/bash

cat <<EOF
=======================================
Issue client certificates
---------------------------------------
Create new certificates against pki 
secrets storage of Vault.
Deploy to pki directory
=======================================
EOF

if [[ -f ./vault.env ]] ; then
  . ./vault.env
else
  echo "Unable to find vault.env file from previous step"
  exit 1
fi

# Test issue ceertificates
if $script2 -c ./script.conf --cert-list client_cert.conf --cert-ttl 86700 --cert-min-ttl 7200 ; then
  echo "It's OK to fail, looks good :)"
else
  echo "ERROR: Deploy failed" >&2
  exit 1
fi

tree $cert_destination

if [[ $(find $cert_destination -type f -name '*.crt' | wc -l) -eq 2 ]] ; then
  echo "Success, looks we have some certificates"
else
  echo "ERROR: Unable to find certificates" >&2
  exit 1
fi
