# Python Implementation of the EVM

[![Join the chat at https://gitter.im/ethereum/py-evm](https://badges.gitter.im/ethereum/py-evm.svg)](https://gitter.im/ethereum/py-evm)
[![Documentation Status](https://readthedocs.org/projects/py-evm/badge/?version=latest)](http://py-evm.readthedocs.io/en/latest/?badge=latest)

[Documentation hosted by ReadTheDocs](http://py-evm.readthedocs.io/en/latest/)


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


## Development
Py-EVM depends on a submodule of the common tests across all clients,
so you need to clone the repo with the `--recursive` flag. Example:

```sh
git clone --recursive git@github.com:ethereum/py-evm.git
```

Py-EVM requires Python 3. Often, the best way to guarantee a clean Python 3 environment is with [`virtualenv`](https://virtualenv.pypa.io/en/stable/), like:

```sh
# once:
$ virtualenv -p python3 venv

# each session:
$ . venv/bin/activate
```

Then install the required python packages via:

```sh
pip install -e .[dev]
```


### Running the tests

You can run the tests with:

```sh
pytest
```

Or you can install `tox` to run the full test suite.


### Releasing

Pandoc is required for transforming the markdown README to the proper format to
render correctly on pypi.

For Debian-like systems:

```
apt install pandoc
```

Or on OSX:

```sh
brew install pandoc
```

To release a new version:

```sh
bumpversion $$VERSION_PART_TO_BUMP$$
git push && git push --tags
make release
```


#### How to bumpversion

The version format for this repo is `{major}.{minor}.{patch}` for stable, and
`{major}.{minor}.{patch}-{stage}.{devnum}` for unstable (`stage` can be alpha or beta).

To issue the next version in line, use bumpversion and specify which part to bump,
like `bumpversion minor` or `bumpversion devnum`.

If you are in a beta version, `bumpversion stage` will switch to a stable.

To issue an unstable version when the current version is stable, specify the
new version explicitly, like `bumpversion --new-version 4.0.0-alpha.1 devnum`
