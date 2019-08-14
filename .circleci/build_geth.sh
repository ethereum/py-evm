#!/usr/bin/env bash

mkdir -p $HOME/.ethash
pip install --user py-geth>=2.1.0
export GOROOT=/usr/local/go
export GETH_BINARY="$HOME/.py-geth/geth-$GETH_VERSION/bin/geth"
if [ ! -e "$GETH_BINARY" ]; then
  curl -O https://storage.googleapis.com/golang/go1.10.linux-amd64.tar.gz
  tar xvf go1.10.linux-amd64.tar.gz
  sudo chown -R root:root ./go
  sudo mv go /usr/local
  sudo ln -s /usr/local/go/bin/go /usr/local/bin/go
  sudo apt-get update;
  sudo apt-get install -y build-essential;
  python -m geth.install $GETH_VERSION;
fi
sudo ln -s $GETH_BINARY /usr/local/bin/geth
geth version
