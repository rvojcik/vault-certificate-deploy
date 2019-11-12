#!/bin/bash

cat <<EOF
=======================================
Clean unused certificates
---------------------------------------
=======================================
EOF

if [[ -f ./vault.env ]] ; then
  . ./vault.env
else
  echo "Unable to find vault.env file from previous step"
  exit 1
fi

tmp_file=$(mktemp)
echo "test1.test.intra" > $tmp_file

# Test renew
if $script2 -c ./script.conf --cert-list $tmp_file --cert-ttl 86700 --cert-min-ttl 90000 ; then
  echo "Success, looks good :)"
else
  echo "ERROR: Deploy clean failed" >&2
  exit 1
fi

tree $cert_destination

if [ $(find $cert_destination -type f -name '*.crt' | wc -l) -eq 1 ] ; then
    echo "Looks good, there should be 1 certificate"
    exit 0
else
    echo "Something wrong, there are more or less certificates. We want 1" >&2
    exit 1
fi

