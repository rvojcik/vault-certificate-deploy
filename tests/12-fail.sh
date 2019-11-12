#!/bin/bash

cat <<EOF
=======================================
FAIL DEPLOY (It's good to fail)
---------------------------------------
Check fail states and correct exitcodes
for wrong cert formats

Clean test-cert from previous step.
No certs should left 
=======================================
EOF

if [[ -f ./vault.env ]] ; then
  . ./vault.env
else
  echo "Unable to find vault.env file from previous step"
  exit 1
fi

# Test fail deploy
if $script -c ./script.conf --cert-list deploy3.conf ; then
  echo "ERROR: Deploy success when certificate was bad." >&2
  exit 1
else
  echo "It's OK to fail, looks good :)"
fi

tree $cert_destination

if [[ $(find $cert_destination -type f -name '*.crt' | wc -l) -gt 0 ]] ; then
  echo "ERROR: There should be no certificates in this step" >&2
  exit 1
else
  echo "Success, no certificates left in this step"
fi
