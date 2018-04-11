Contributing to py-evm
----------------------

First we need to clone the Py-EVM repository. Py-EVM depends on a submodule of the common tests across all clients, so we need to clone the repo with the ``--recursive`` flag. Example:

.. code:: sh

    $ git clone --recursive https://github.com/ethereum/py-evm.git


Py-EVM requires Python 3. Often, the best way to guarantee a clean Python 3 environment is with `virtualenv <https://virtualenv.pypa.io/en/stable/>`_, like:

.. code:: sh

    # once:
    $ virtualenv -p python3 venv

    # each session:
    $ . venv/bin/activate

After we have activated our virtual environment, installing all dependencies that are needed to run, develop and test all code in this repository is as easy as:

.. code:: sh

    pip install -e .[dev]


Running the tests
~~~~~~~~~~~~~~~~~

A great way to explore the code base is to run the tests.

We can run all tests with:

.. code:: sh

    pytest

However, running the entire test suite does take a very long time so often we just want to run a subset instead, like:

.. code:: sh

    pytest tests/core/padding-utils/test_padding.py


We can also install ``tox`` to run the full test suite which also covers things like testing the code against different Python versions, linting etc.

It is important to understand that each Pull Request must pass the full test suite as part of the CI check, hence it is often convenient to have ``tox`` installed locally as well.


Releasing
~~~~~~~~~

Pandoc is required for transforming the markdown README to the proper
format to render correctly on pypi.

For Debian-like systems:

::

    apt install pandoc

Or on OSX:

.. code:: sh

    brew install pandoc

To release a new version:

.. code:: sh

    bumpversion $$VERSION_PART_TO_BUMP$$
    git push && git push --tags
    make release

How to bumpversion
^^^^^^^^^^^^^^^^^^

The version format for this repo is ``{major}.{minor}.{patch}`` for
stable, and ``{major}.{minor}.{patch}-{stage}.{devnum}`` for unstable
(``stage`` can be alpha or beta).

To issue the next version in line, use bumpversion and specify which
part to bump, like ``bumpversion minor`` or ``bumpversion devnum``.

If you are in a beta version, ``bumpversion stage`` will switch to a
stable.

To issue an unstable version when the current version is stable, specify
the new version explicitly, like
``bumpversion --new-version 4.0.0-alpha.1 devnum``


