# Python Implementation of the Ethereum protocol

[![Join the chat at https://gitter.im/ethereum/py-evm](https://badges.gitter.im/ethereum/py-evm.svg)](https://gitter.im/ethereum/py-evm)
[![Documentation Status](https://readthedocs.org/projects/py-evm/badge/?version=latest)](http://py-evm.readthedocs.io/en/latest/?badge=latest)


## Py-EVM

Py-EVM is a new implementation of the Ethereum protocol in Python. It contains the low level
primitives for the existing Ethereum 1.0 chain as well as emerging support for the upcoming
Ethereum 2.0 / Serenity spec.

### Goals

Py-EVM aims to eventually become the defacto Python implementation of the Ethereum protocol,
enabling a wide array of use cases for both public and private chains. 

In particular Py-EVM aims to:

- be a reference implementation of the Ethereum 1.0 and 2.0 implementation in one of the most widely used and understood languages, Python.

- be easy to understand and modifiable

- have clear and simple APIs

- come with solid, friendly documentation

- deliver the low level primitives to build various clients on top (including *full* and *light* clients)

- be highly flexible to support both research as well as alternate use cases like private chains.

## Trinity

While Py-EVM provides the low level APIs of the Ethereum protocol, it does not aim to implement a
full or light node directly.

### Goals

- provide a reference implementation for an Ethereum 1.0 node (alpha)

- support "full" and "light" modes

- fully support mainnet as well as several testnets

- provide a reference implementation of an Ethereum 2.0 / Serenity beacon node (pre-alpha)

- provide a reference implementation of an Ethereum 2.0 / Sereneity validator node (pre-alpha)


## Quickstart

[Get started in 5 minutes](https://py-evm.readthedocs.io/en/latest/quickstart.html)

## Documentation

Check out the [documentation on our official website](http://py-evm.readthedocs.io/en/latest/)

## Want to help?

Want to file a bug, contribute some code, or improve documentation? Excellent! Read up on our
guidelines for [contributing](https://py-evm.readthedocs.io/en/latest/contributing.html) and then check out one of our issues that are labeled [Good First Issue](https://github.com/ethereum/py-evm/issues?q=is%3Aissue+is%3Aopen+label%3A%22Good+First+Issue%22).
