#!/bin/bash

# Run this once, but it does not hurt to run it every time
file_dir="$(dirname "$0")"
geth --datadir ~/.ethereum/net42 init $(dirname "$0")/genesis.json
# Run this every time you start your Geth "42", and add flags here as you need
# geth --datadir ~/.ethereum/net42 --networkid 42
geth --datadir=~/.ethereum/net42 --networkid 42 --rpc --rpcport 8545 --rpcaddr 127.0.0.1 --rpccorsdomain "*" --rpcapi "eth,net,web3,personal,miner" --nodiscover console
# geth --datadir=~/.ethereum/net42 --networkid 42 --rpc --rpcport 8545 --rpcaddr 127.0.0.1 --rpccorsdomain "*" --rpcapi "*" console

