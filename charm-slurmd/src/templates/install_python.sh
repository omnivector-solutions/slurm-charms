#!/bin/bash

PYTHON38_VERSION="3.8.10"

echo "Downloading and installing Python $PYTHON38_VERSION"

mkdir ./tmp/
wget https://www.python.org/ftp/python/${PYTHON38_VERSION}/Python-${PYTHON38_VERSION}.tgz -P ./tmp/
tar xvf ./tmp/Python-${PYTHON38_VERSION}.tgz -C ./tmp/
cd ./tmp/Python-${PYTHON38_VERSION}/
./configure --enable-optimizations --prefix=/usr
make altinstall
cd ../../
rm -rf tmp/

cp /usr/bin/python3.8 /usr/bin/python3
cp /usr/bin/pip3.8 /usr/bin/pip3
cp /usr/bin/pip3.8 /usr/bin/pip
