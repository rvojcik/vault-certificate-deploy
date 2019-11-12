#!/bin/bash

cat <<EOF
=======================================
Renew client certificates
---------------------------------------
Check renew functionality
When expiration of certificate is in place
we automaticly renew certificate
=======================================
EOF

if [[ -f ./vault.env ]] ; then
  . ./vault.env
else
  echo "Unable to find vault.env file from previous step"
  exit 1
fi

tmp_file=$(mktemp)

find $cert_destination -type f -name '*.crt' -exec md5sum {} \; > $tmp_file

# Test renew
if $script2 -c ./script.conf --cert-list client_cert.conf --cert-ttl 86700 --cert-min-ttl 90000 ; then
  echo "It's OK to fail, looks good :)"
else
  echo "ERROR: Deploy failed" >&2
  exit 1
fi

tree $cert_destination

if [ $(diff <(find $cert_destination -type f -name '*.crt' -exec md5sum {} \;) $tmp_file | egrep '^>' | wc -l) -eq 2 ] ; then
    echo "Looks good, 2 certificates changed"
    rm $tmp_file
    exit 0
else
    echo "Something wrong, 2 certificates should change but CRC is not OK" >&2
    rm $tmp_file
    exit 1
fi

