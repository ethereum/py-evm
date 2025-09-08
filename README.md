> [!caution]
> This repository has been archived, and is now read-only. For a Python implementation of the EVM, check out the [execution-specs](https://github.com/ethereum/execution-specs) repo.

# Python Implementation of the Ethereum protocol

[![PyPI version](https://badge.fury.io/py/py-evm.svg)](https://badge.fury.io/py/py-evm)
[![Python versions](https://img.shields.io/pypi/pyversions/py-evm.svg)](https://pypi.python.org/pypi/py-evm)
[![Docs build](https://readthedocs.org/projects/py-evm/badge/?version=latest)](https://py-evm.readthedocs.io/en/latest/?badge=latest)

## Py-EVM

Py-EVM is an implementation of the Ethereum Virtual Machine (EVM) in Python.

### Goals

Py-EVM aims to be a readable yet generally performant version of the EVM in Python.

In particular Py-EVM aims to:

- be easy to understand and modifiable
- be highly flexible to support research and experimentation
- be performant enough to be used in testing for Python projects
- be a reference implementation of the Ethereum execution layer specifications

Ethereum consensus today is achieved via Proof of Stake, involving a consensus layer that
is beyond the scope of this repository.

## Installation

```sh
python -m pip install py-evm
```

## Documentation

[Get started in 5 minutes](https://py-evm.readthedocs.io/en/latest/guides/building_an_app_that_uses_pyevm.html)

Check out the [documentation on our official website](https://py-evm.readthedocs.io/en/latest/)

View the [change log](https://py-evm.readthedocs.io/en/latest/release_notes.html).
