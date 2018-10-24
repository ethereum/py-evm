#!/usr/bin/env bash

set -o errexit
set -o nounset

sudo apt-get install -y liblz4-dev libsnappy-dev libgflags-dev zlib1g-dev libbz2-dev libzstd-dev


if [ ! -d "/home/circleci/rocksdb" ]; then
  git clone https://github.com/facebook/rocksdb /home/circleci/rocksdb
fi
if [ ! -f "/home/circleci/rocksdb/librocksdb.so.5.8.8" ]; then
  cd /home/circleci/rocksdb/ && git checkout v5.8.8 && sudo make install-shared INSTALL_PATH=/usr
fi
if [ ! -f "/usr/lib/librocksdb.so.5.8" ]; then
  ln -fs /home/circleci/rocksdb/librocksdb.so.5.8.8 /usr/lib/librocksdb.so.5.8
fi
if [ ! -f "/usr/lib/librocksdb.so.5" ]; then
  ln -fs /home/circleci/rocksdb/librocksdb.so.5.8.8 /usr/lib/librocksdb.so.5
fi
if [ ! -f "/usr/lib/librocksdb.so" ]; then
  ln -fs /home/circleci/rocksdb/librocksdb.so.5.8.8 /usr/lib/librocksdb.so
fi  
