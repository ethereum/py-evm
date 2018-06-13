#!/usr/bin/env bash

# to get the add-apt-repository command
sudo apt-get install software-properties-common

sudo add-apt-repository -y ppa:ethereum/ethereum
sudo add-apt-repository -y ppa:ethereum/ethereum-dev
sudo sed -i 's/cosmic/bionic/g' /etc/apt/sources.list.d/ethereum-ubuntu-ethereum-cosmic.list
sudo sed -i 's/cosmic/bionic/g' /etc/apt/sources.list.d/ethereum-ubuntu-ethereum-dev-cosmic.list
sudo apt-get -y update
sudo apt-get install -y --allow-unauthenticated solc