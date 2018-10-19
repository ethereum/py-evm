#!/usr/bin/env bash

sudo apt-get install -y liblz4-dev libsnappy-dev libgflags-dev zlib1g-dev libbz2-dev libzstd-dev
if [ ! -f "/root/project/rocksdb" ]; then
  git clone https://github.com/facebook/rocksdb
fi
if [ ! -f "/root/project/rocksdb/librocksdb.a" ]; then
  cd rocksdb/ && git checkout v5.8.8 && sudo make install-shared INSTALL_PATH=/usr
fi  
