# Python Implementation of the Ethereum protocol

[![Join the conversation on Discord](https://img.shields.io/discord/809793915578089484?color=blue&label=chat&logo=discord&logoColor=white)](https://discord.gg/GHryRvPB84)
[![Build Status](https://circleci.com/gh/ethereum/py-evm.svg?style=shield)](https://circleci.com/gh/ethereum/py-evm)
[![PyPI version](https://badge.fury.io/py/py-evm.svg)](https://badge.fury.io/py/py-evm)
[![Python versions](https://img.shields.io/pypi/pyversions/py-evm.svg)](https://pypi.python.org/pypi/py-evm)
[![Docs build](https://readthedocs.org/projects/py-evm/badge/?version=latest)](https://py-evm.readthedocs.io/en/latest/?badge=latest)

## Py-EVM

Py-EVM is an implementation of the Ethereum protocol in Python. It contains the low level
primitives for the original proof-of-work (POW), (formerly known as Ethereum 1.0) chain
as well as emerging support for the proof-of-stake (POS) (formerly known as Ethereum 2.0) spec.

### Goals

Py-EVM aims to eventually become the defacto Python implementation of the Ethereum protocol,
enabling a wide array of use cases for both public and private chains.

In particular Py-EVM aims to:

- be a reference implementation of the Ethereum POW and POS implementations in one of the most widely used and understood languages, Python.

- be easy to understand and modifiable

- have clear and simple APIs

- come with solid, friendly documentation

- deliver the low level primitives to build various clients on top (including *full* and *light* clients)

- be highly flexible to support both research as well as alternate use cases like private chains.

## Installation

```sh
python -m pip install py-evm
```

## Documentation

[Get started in 5 minutes](https://py-evm.readthedocs.io/en/latest/guides/building_an_app_that_uses_pyevm.html)

Check out the [documentation on our official website](https://py-evm.readthedocs.io/en/latest/)

View the [change log](https://py-evm.readthedocs.io/en/latest/release_notes.html).
