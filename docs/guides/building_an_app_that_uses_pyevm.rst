Building an app that uses Py-EVM
================================

One of the primary use cases of the ``Py-EVM`` library is to enable developers to build applications
that want to interact with the ethereum ecosystem.

In this guide we want to build a very simple script that uses the ``Py-EVM`` library to create a
fresh blockchain with a pre-funded address to simply read the balance of that address through the
regular ``Py-EVM`` APIs. Frankly, not the most exciting application in the world, but the principle
of how we use the ``Py-EVM`` library stays the same for more exciting use cases.


Setting up the application
--------------------------

Let's get started by setting up a new application. Often, that process involves lots of repetitive
boilerplate code, so instead of doing it all by hand, let's just clone the
`Ethereum Python Project Template <https://github.com/carver/ethereum-python-project-template>`_
which contains all the typical things that we want.

To clone this into a new directory ``demo-app`` run:

.. code:: sh

  git clone https://github.com/carver/ethereum-python-project-template.git demo-app

Then, change into the directory

.. code:: sh

  cd demo-app


Add the Py-EVM library as a dependency
--------------------------------------

To add ``Py-EVM`` as a dependency, open the ``setup.py`` file in the root directory of the application
and change the ``install_requires`` section as follows.

.. code-block:: python

  install_requires=[
      "eth-utils>=1,<2",
      "py-evm==0.3.0a20",
  ],

.. warning::

  Make sure to also change the ``name`` inside the ``setup.py`` file to something valid
  (e.g. ``demo-app``) or otherwise, fetching dependencies will fail.

Next, we need to use the ``pip`` package manager to fetch and install the dependencies of our app.

.. note::
  .. include:: /fragments/virtualenv_explainer.rst


To install the dependencies, run:

.. code:: sh

  pip install -e .[dev]

Congrats! We're now ready to build our application!

Writing the application code
----------------------------

Next, we'll create a new directory ``app`` and create a file ``main.py`` inside. Paste in the following content.

.. include:: /fragments/doctest_explainer.rst

.. doctest::

  >>> from eth import constants
  >>> from eth.chains.mainnet import MainnetChain
  >>> from eth.db.atomic import AtomicDB

  >>> from eth_utils import to_wei, encode_hex


  >>> MOCK_ADDRESS = constants.ZERO_ADDRESS
  >>> DEFAULT_INITIAL_BALANCE = to_wei(10000, 'ether')

  >>> GENESIS_PARAMS = {
  ...     'parent_hash': constants.GENESIS_PARENT_HASH,
  ...     'uncles_hash': constants.EMPTY_UNCLE_HASH,
  ...     'coinbase': constants.ZERO_ADDRESS,
  ...     'transaction_root': constants.BLANK_ROOT_HASH,
  ...     'receipt_root': constants.BLANK_ROOT_HASH,
  ...     'difficulty': constants.GENESIS_DIFFICULTY,
  ...     'block_number': constants.GENESIS_BLOCK_NUMBER,
  ...     'gas_limit': constants.GENESIS_GAS_LIMIT,
  ...     'extra_data': constants.GENESIS_EXTRA_DATA,
  ...     'nonce': constants.GENESIS_NONCE
  ... }

  >>> GENESIS_STATE = {
  ...     MOCK_ADDRESS: {
  ...         "balance": DEFAULT_INITIAL_BALANCE,
  ...         "nonce": 0,
  ...         "code": b'',
  ...         "storage": {}
  ...     }
  ... }

  >>> chain = MainnetChain.from_genesis(AtomicDB(), GENESIS_PARAMS, GENESIS_STATE)

  >>> mock_address_balance = chain.get_vm().state.get_balance(MOCK_ADDRESS)

  >>> print("The balance of address {} is {} wei".format(
  ...     encode_hex(MOCK_ADDRESS),
  ...     mock_address_balance)
  ... )
  The balance of address 0x0000000000000000000000000000000000000000 is 10000000000000000000000 wei

Runing the script
-----------------

Let's run the script by invoking the following command.

.. code:: sh

  python app/main.py

We should see the following output.

.. code:: sh

  The balance of address 0x0000000000000000000000000000000000000000 is 10000000000000000000000 wei
