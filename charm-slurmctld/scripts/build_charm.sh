#!/bin/bash

set -eux

rm -rf build/
rm -rf out/
mkdir build/
mkdir out/

cp -r src/ build/
cp -r scripts/ build/
cp metadata.yaml build/
cp config.yaml build/

cat <<EOF >build/dispatch
#!/bin/sh
JUJU_DISPATCH_PATH="\${JUJU_DISPATCH_PATH:-\$0}" PYTHONPATH=lib:venv/lib/python3.8/site-packages ./venv/bin/python ./src/charm.py
EOF
chmod +x build/dispatch

mkdir build/hooks
cd build/hooks

ln -s ../dispatch install
ln -s ../dispatch start
ln -s ../dispatch upgrade-charm
