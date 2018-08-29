Builder Tools
=============


The JSON test fillers found in `eth.tools.fixtures` is a set of tools which facilitate
creating standard JSON consensus tests as found in the
`ethereum/tests repository <https://github.com/ethereum/tests>`_. 

.. note:: Only VM and state tests are supported right now.


State Test Fillers
------------------

Tests are generated in two steps. 

* First, a *test filler* is written that contains a high level description of the test case.
* Subsequently, the filler is compiled to the actual test in a process called
  filling, mainly consisting of calculating the resulting state root.

The test builder represents each stage as a nested dictionary. Helper functions are provided to
assemble the filler file step by step in the correct format. The
:func:`~eth.tools.fixtures.fillers.fill_test` function handles compilation and
takes additional parameters that can't be inferred from the filler.


Creating a Filler
~~~~~~~~~~~~~~~~~

Fillers are generated in a functional fashion by piping a dictionary through a
sequence of functions.

.. code-block:: python

    filler = pipe(
        setup_main_filler("test"),
        pre_state(
            (sender, "balance", 1),
            (receiver, "balance", 0),
        ),
        expect(
            networks=["Frontier"],
            transaction={
                "to": receiver,
                "value": 1,
                "secretKey": sender_key,
            },
            post_state=[
                [sender, "balance", 0],
                [receiver, "balance", 1],
            ]
        )
    )

.. note:: 

    Note that :func:`~eth.tools.fixtures.setup_filler` returns a
    dictionary, whereas all of the following functions such as
    :func:`~eth.tools.fixtures.pre_state`,
    :func:`~eth.tools.fixtures.expect`, expect to be passed a dictionary
    as their single argument and return an updated version of the dictionary.

.. automodule:: eth.tools.fixtures.fillers
  :noindex:
  :members: setup_main_filler


This function kicks off the filler generation process by creating the general filler scaffold with
a test name and general information about the testing environment.

For tests for the main chain, the `environment` parameter is expected to be a dictionary with some
or all of the following keys:

+------------------------+---------------------------------+
| key                    | description                     |
+========================+=================================+
| ``"currentCoinbase"``  | the coinbase address            |
+------------------------+---------------------------------+
| ``"currentNumber"``    | the block number                |
+------------------------+---------------------------------+
| ``"previousHash"``     | the hash of the parent block    |
+------------------------+---------------------------------+
| ``"currentDifficulty"``| the block's difficulty          |
+------------------------+---------------------------------+
| ``"currentGasLimit"``  | the block's gas limit           |
+------------------------+---------------------------------+
| ``"currentTimestamp"`` | the timestamp of the block      |
+------------------------+---------------------------------+

.. automodule:: eth.tools.fixtures.fillers
  :noindex:
  :members: pre_state


This function specifies the state prior to the test execution. Multiple invocations don't override
the state but extend it instead.

In general, the elements of `state_definitions` are nested dictionaries of the following form:

.. code-block:: python

    {
        address: {
            "nonce": <account nonce>,
            "balance": <account balance>,
            "code": <account code>,
            "storage": {
                <storage slot>: <storage value>
            }
        }
    }

To avoid unnecessary nesting especially if only few fields per account are specified, the following
and similar formats are possible as well:

.. code-block:: python

    (address, "balance", <account balance>)
    (address, "storage", <storage slot>, <storage value>)
    (address, "storage", {<storage slot>: <storage value>})
    (address, {"balance", <account balance>})

.. automodule:: eth.tools.fixtures.fillers
  :noindex:
  :members: execution


For VM tests, this function specifies the code that is being run as well as the current state of
the EVM. State tests don't support this object. The parameter is a dictionary specifying some or
all of the following keys:

+--------------------+------------------------------------------------------------+
|  key               | description                                                |
+====================+============================================================+
| ``"address"``      | the address of the account executing the code              |
+--------------------+------------------------------------------------------------+
| ``"caller"``       | the caller address                                         |
+--------------------+------------------------------------------------------------+
| ``"origin"``       | the origin address (defaulting to the caller address)      |
+--------------------+------------------------------------------------------------+
| ``"value"``        | the value of the call                                      |
+--------------------+------------------------------------------------------------+
| ``"data"``         | the data passed with the call                              |
+--------------------+------------------------------------------------------------+
| ``"gasPrice"``     | the gas price of the call                                  |
+--------------------+------------------------------------------------------------+
| ``"gas"``          | the amount of gas allocated for the call                   |
+--------------------+------------------------------------------------------------+
| ``"code"``         | the bytecode to execute                                    |
+--------------------+------------------------------------------------------------+
| ``"vyperLLLCode"`` | the code in Vyper LLL (compiled to bytecode automatically) |
+--------------------+------------------------------------------------------------+


.. automodule:: eth.tools.fixtures.fillers
  :noindex:
  :members: expect


This specifies the expected result of the test.

For state tests, multiple expectations can be given, differing in the transaction data, gas
limit, and value, in the applicable networks, and as a result also in the post state. VM tests
support only a single expectation with no specified network and no transaction (here, its role is
played by :func:`~eth.tools.fixtures.fillers.execution`).

* ``post_state`` is a list of state definition in the same form as expected
    by :func:`~eth.tools.fixtures.fillers.pre_state`. State items that are
    not set explicitly default to their pre state.

* ``networks`` defines the forks under which the expectation is applicable. It should be a sublist of
    the following identifiers (also available in `ALL_FORKS`):

    * ``"Frontier"``
    * ``"Homestead"``
    * ``"EIP150"``
    * ``"EIP158"``
    * ``"Byzantium"``

* ``transaction`` is a dictionary coming in two variants. For the main shard:

    +----------------+-------------------------------+
    | key            | description                   |
    +================+===============================+
    | ``"data"``     | the transaction data,         |
    +----------------+-------------------------------+
    | ``"gasLimit"`` | the transaction gas limit,    |
    +----------------+-------------------------------+
    | ``"gasPrice"`` | the gas price,                |
    +----------------+-------------------------------+
    | ``"nonce"``    | the transaction nonce,        |
    +----------------+-------------------------------+
    | ``"value"``    | the transaction value         |
    +----------------+-------------------------------+

In addition, one should specify either the signature itself (via keys ``"v"``, ``"r"``, and ``"s"``) or
a private key used for signing (via ``"secretKey"``).
