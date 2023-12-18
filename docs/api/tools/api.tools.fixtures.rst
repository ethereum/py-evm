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


.. autofunction:: eth.tools.fixtures.fillers.common.setup_main_filler

.. autofunction:: eth.tools.fixtures.fillers.pre_state

.. autofunction:: eth.tools.fixtures.fillers.execution

.. autofunction:: eth.tools.fixtures.fillers.expect
