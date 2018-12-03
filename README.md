# Python Implementation of the EVM

[![Join the chat at https://gitter.im/ethereum/py-evm](https://badges.gitter.im/ethereum/py-evm.svg)](https://gitter.im/ethereum/py-evm)
[![Documentation Status](https://readthedocs.org/projects/py-evm/badge/?version=latest)](http://py-evm.readthedocs.io/en/latest/?badge=latest)


## Introducing Py-EVM

Py-EVM is a new implementation of the Ethereum Virtual Machine written in
python. It is currently in active development but is quickly progressing
through the test suite provided by ethereum/tests. We have Vitalik, and the
existing PyEthereum code to thank for the quick progress we’ve made as many
design decisions were inspired, or even directly ported from the PyEthereum
codebase.

### Goals

Py-EVM aims to eventually become the defacto Python implementation of the EVM,
enabling a wide array of use cases for both public and private chains. Development will focus on creating an EVM with a well defined API, friendly and
easy to digest documentation which can be run as a fully functional mainnet
node.

In particular Py-EVM aims to:

- be an example implementation of the EVM in one of the most widely used and understood languages, Python.

- deliver the low level APIs for clients to build full or light nodes on top of

- be easy to understand and modifiable

- be highly flexible to support both research as well as alternate use cases like private chains.

### Trinity

While Py-EVM provides the low level APIs of the EVM, it does not aim to implement a full or light node directly.

We provide a base implementation of a full node called Trinity that is based on Py-EVM.

In the future there may be alternative clients based on the Py-EVM.

### Step 1: Alpha Release

The plan is to begin with an MVP, alpha-level release that is suitable for
testing purposes. We’ll be looking for early adopters to provide feedback on
our architecture and API choices as well as general feedback and bug finding.

#### Blog posts:

- https://medium.com/@pipermerriam/py-evm-part-1-origins-25d9ad390b


## Quickstart

[Get started in 5 minutes](https://py-evm.readthedocs.io/en/latest/quickstart.html)

## Documentation

Check out the [documentation on our official website](http://py-evm.readthedocs.io/en/latest/)

## Want to help?

Want to file a bug, contribute some code, or improve documentation? Excellent! Read up on our
guidelines for [contributing](https://py-evm.readthedocs.io/en/latest/contributing.html) and then check out one of our issues that are labeled [Good First Issue](https://github.com/ethereum/py-evm/issues?q=is%3Aissue+is%3Aopen+label%3A%22Good+First+Issue%22).
