# Python Implementation of the EVM

[![Join the chat at https://gitter.im/ethereum/py-evm](https://badges.gitter.im/ethereum/py-evm.svg)](https://gitter.im/ethereum/py-evm)
[![Documentation Status](https://readthedocs.org/projects/py-evm/badge/?version=latest)](http://py-evm.readthedocs.io/en/latest/?badge=latest)

[Documentation hosted by ReadTheDocs](http://py-evm.readthedocs.io/en/latest/)


# Casper Implementation

This branch will be focused on porting Casper FFG to py-evm.

See [IMPLEMENTATION.md](https://github.com/ethereum/casper/blob/master/IMPLEMENTATION.md)


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
