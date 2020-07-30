#!/bin/bash

set -eux

mkdir build/
mkdir out/

if ! [[ -f requirements.txt ]]; then
    echo "Missing reuirements.txt"
    exit -1
fi

docker run -it --rm \
    -v `pwd`/requirements.txt:/srv/requirements.txt \
    -v `pwd`/build:/srv/build \
    quay.io/pypa/manylinux2014_x86_64 \
    /bin/sh -c '/opt/python/cp38-cp38/bin/python -m venv --copies --clear /srv/build/venv && \
                /opt/python/cp38-cp38/bin/pip install -r /srv/requirements.txt \
                -t /srv/build/venv/lib/python3.8/site-packages && \
                cp -r /usr/local/lib/libcrypt.* /srv/build/venv/lib/ && \
                cp -r /opt/_internal/cpython-3.8.5/lib/python3.8 /srv/build/venv/lib/ && \
                cp -r /opt/_internal/cpython-3.8.5/include/* /srv/build/venv/include/ && \
                chown -R 1000:1000 /srv/build'


for charm in slurmd slurmctld slurmdbd; do
    dir=charm-$charm
    mkdir -p build/$dir/hooks
    cp $dir/metadata.yaml build/$dir/
    cp $dir/config.yaml build/$dir/
    cp -r $dir/src build/$dir/
    cp -r build/venv build/$dir/
    cat <<EOF >build/$dir/dispatch
#!/bin/sh
PYTHONHOME=venv/ LD_LIBRARY_PATH="\${LD_LIBRARY_PATH}:venv/lib/" JUJU_DISPATCH_PATH="\${JUJU_DISPATCH_PATH:-\$0}" PYTHONPATH=lib:venv/lib/python3.8/site-packages ./venv/bin/python ./src/charm.py
EOF
    chmod +x build/$dir/dispatch

    cd build/$dir/hooks/
    ln -s ../dispatch install
    ln -s ../dispatch start
    ln -s ../dispatch upgrade-charm
    cd ../../../
    ./scripts/create_charm_zip.py build/$dir $charm
done

# clean up
rm -rf out/venv
