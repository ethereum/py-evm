#!/bin/bash

LIBP2P_DAEMON_VERSION=de7ca07
GOPACKAGE=go1.11.5.linux-amd64.tar.gz
LIBP2P_DAEMON_REPO=github.com/libp2p/go-libp2p-daemon

P2PD_DIR=$HOME/.p2pd/$LIBP2P_DAEMON_VERSION
P2PD_BINARY=$P2PD_DIR/p2pd
if [ ! -e "$P2PD_BINARY" ]; then
    wget https://dl.google.com/go/$GOPACKAGE
    sudo tar -C /usr/local -xzf $GOPACKAGE
    export GOPATH=$HOME/go
    export GOROOT=/usr/local/go
    export PATH=$GOROOT/bin:$GOPATH/bin:$PATH
    go version
    go get $LIBP2P_DAEMON_REPO
    cd $GOPATH/src/$LIBP2P_DAEMON_REPO
    git checkout $LIBP2P_DAEMON_VERSION
    make bin
    mkdir -p $P2PD_DIR
    cp `which p2pd` $P2PD_BINARY
fi
sudo ln -s $P2PD_BINARY /usr/local/bin/p2pd
