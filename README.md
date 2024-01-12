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

## Quickstart

```sh
python -m pip install py-evm
```

[Get started in 5 minutes](https://py-evm.readthedocs.io/en/latest/guides/quickstart.html)

## Documentation

Check out the [documentation on our official website](https://py-evm.readthedocs.io/en/latest/)

## Developer Setup

If you would like to hack on py-evm, please check out the [Snake Charmers
Tactical Manual](https://github.com/ethereum/snake-charmers-tactical-manual)
for information on how we do:

- Testing
- Pull Requests
- Documentation

We use [pre-commit](https://pre-commit.com/) to maintain consistent code style. Once
installed, it will run automatically with every commit. You can also run it manually
with `make lint`. If you need to make a commit that skips the `pre-commit` checks, you
can do so with `git commit --no-verify`.

### Development Environment Setup

```sh
git clone git@github.com:ethereum/py-evm.git
cd py-evm
virtualenv -p python3 venv
. venv/bin/activate
python -m pip install -e ".[dev]"
pre-commit install
```

### Release setup

To release a new version:

```sh
make release bump=$$VERSION_PART_TO_BUMP$$
```

To issue the next version in line, specify which part to bump,
like `make release bump=minor` or `make release bump=devnum`. This is typically done from the
main branch, except when releasing a beta (in which case the beta is released from main,
and the previous stable branch is released from said branch).

## Want to help?

Want to file a bug, contribute some code, or improve documentation? Excellent! Read up on our
guidelines for [contributing](https://py-evm.readthedocs.io/en/latest/contributing.html) and then check out one of our issues that are labeled [Good First Issue](https://github.com/ethereum/py-evm/issues?q=is%3Aissue+is%3Aopen+label%3A%22Good+First+Issue%22).
