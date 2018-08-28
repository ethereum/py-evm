Builders
========


Chain Builder
-------------

The chain builder utils are intended to reduce common boilerplace for both
construction of chain classes as well as building up some desired chain state.

.. note:: These tools are best used in conjunction with ``cytoolz.pipe``.


Constructing Chain Classes
~~~~~~~~~~~~~~~~~~~~~~~~~~

The following utilities are provided to assist with constructing a chain class.


.. autofunction:: eth.tools.builder.chain.fork_at


.. autofunction:: eth.tools.builder.chain.dao_fork_at


.. autofunction:: eth.tools.builder.chain.disable_dao_fork


.. autofunction:: eth.tools.builder.chain.enable_pow_mining


.. autofunction:: eth.tools.builder.chain.disable_pow_check


.. autofunction:: eth.tools.builder.chain.name


Initializing Chains
~~~~~~~~~~~~~~~~~~~

The following utilities are provided to assist with initializing a chain into
the genesis state.

.. autofunction:: eth.tools.builder.chain.genesis

    Initializes the given chain class with the given genesis header parameters
    and chain state.


Building Chains
~~~~~~~~~~~~~~~

The following utilities are provided to assist with building out chains of
blocks.


.. autofunction:: eth.tools.builder.chain.copy

    Provides a copy of the chain at the given state.  Actions performed on the
    resulting chain will not be represented on the original chain.


.. autofunction:: eth.tools.builder.chain.import_block

    Imports the provided ``block`` into the chain.


.. autofunction:: eth.tools.builder.chain.import_blocks

    Variadic argument version of :func:`~eth.tools.builder.chain.import_block`

.. autofunction:: eth.tools.builder.chain.mine_block

    Mines a new block on the chain.  Header parameters for the new block can be
    overridden using keyword arguments.

.. autofunction:: eth.tools.builder.chain.mine_blocks

    Variadic argument version of :func:`~eth.tools.builder.chain.mine_block`

.. autofunction:: eth.tools.builder.chain.chain_split

    Allows construction of concurrent forks of the chain.  

    Any number of forks may be executed.  For each fork, provide an iterable of
    commands.
    
    The ``exit_fn`` should accept a single argument which is a multidimensional
    array of the outputs from each sequence of operations performed on each
    fork.


.. autofunction:: eth.tools.builder.chain.at_block_number

    Rewinds the chain back to the given block number.  Calls to things like
    ``get_canonical_head`` will still return the canonical head of the chain,
    however, you can use ``mine_block`` to mine fork chains.
