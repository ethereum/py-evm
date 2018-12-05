Contributing
------------

Thank you for your interest in contributing! We welcome all contributions no matter their size. Please read along to learn how to get started. If you get stuck, feel free to reach for help in our `Gitter channel <https://gitter.im/ethereum/py-evm>`_.

Setting the stage
~~~~~~~~~~~~~~~~~

First we need to clone the Py-EVM repository. Py-EVM depends on a submodule of the common tests across all clients, so we need to clone the repo with the ``--recursive`` flag. Example:

.. code:: sh

    $ git clone --recursive https://github.com/ethereum/py-evm.git



.. include:: /fragments/virtualenv_explainer.rst

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

Code Style
~~~~~~~~~~

When multiple people are working on the same body of code, it is important that they write code that conforms to a similar style. It often doesn't matter as much which style, but rather that they conform to one style.

To ensure your contribution conforms to the style being used in this project, we encourage you to read our `style guide <https://github.com/pipermerriam/ethereum-dev-tactical-manual/blob/master/style-guide.md>`_.



Type Hints
~~~~~~~~~~

The code bases is transitioning to use `type hints <https://www.python.org/dev/peps/pep-0484/>`_. Type hints make it easy to prevent certain types of bugs, enable richer tooling and enhance the documentation, making the code easier to follow.

All new code is required to land with type hints with the exception of test code that is not expected to use type hints.

All parameters as well as the return type of defs are expected to be typed with the exception of ``self`` and ``cls`` as seen in the following example.

.. code:: python

    def __init__(self, wrapped_db: BaseDB) -> None:
        self.wrapped_db = wrapped_db
        self.reset()

Documentation
~~~~~~~~~~~~~

Good documentation will lead to quicker adoption and happier users. Please check out our guide
on `how to create documentation for the Python Ethereum ecosystem <https://github.com/ethereum/snake-charmers-tactical-manual/blob/master/documentation.md>`_.


Pull Requests
~~~~~~~~~~~~~

It's a good idea to make pull requests early on.  A pull request represents the
start of a discussion, and doesn't necessarily need to be the final, finished
submission.

GitHub's documentation for working on pull requests is `available here <https://help.github.com/articles/about-pull-requests/>`_.

Once you've made a pull request take a look at the Circle CI build status in the
GitHub interface and make sure all tests are passing. In general pull requests that do not pass the CI build yet won't get reviewed unless explicitly requested.

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


How to release docker images
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To create a docker image:

.. code:: sh

    make create-docker-image version=<version>


By default, this will create a new image with two tags pointing to it:
 - ``ethereum/trinity:<version>`` (explicit version)
 - ``ethereum/trinity:latest`` (latest until overwritten with a future "latest")

Then, push to docker hub:

.. code:: sh

    docker push ethereum/trinity:<version>
    # the following may be left out if we were pushing a patch for an older version
    docker push ethereum/trinity:latest
