#!/bin/bash

set -e 

echo "Entering directory $1"
cd $1/

apt-get update
apt-get install -y $(cat tests/system-requirements.txt)
pip install -r requirements.txt
python setup.py install
run-parts --exit-on-error --regex '^[0-9]+.*\.sh$' ./tests/
