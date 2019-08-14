#!/usr/bin/env bash

if [ ! -d "./eth2-fixtures/tests" ]; then
  wget -c https://github.com/hwwhww/eth2.0-spec-tests/releases/download/v0.8.1b/archive.tar.gz
  tar zxvf archive.tar.gz -C ./eth2-fixtures
fi
