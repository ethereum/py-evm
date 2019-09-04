#!/usr/bin/env bash

if [ ! -d "./eth2-fixtures/tests" ]; then
  wget -c https://github.com/ethereum/eth2.0-spec-tests/releases/download/v0.8.3/general.tar.gz
  wget -c https://github.com/ethereum/eth2.0-spec-tests/releases/download/v0.8.3/mainnet.tar.gz
  wget -c https://github.com/ethereum/eth2.0-spec-tests/releases/download/v0.8.3/minimal.tar.gz
  mkdir eth2-fixtures
  tar zxvf general.tar.gz -C ./eth2-fixtures
  tar zxvf mainnet.tar.gz -C ./eth2-fixtures
  tar zxvf minimal.tar.gz -C ./eth2-fixtures
fi
