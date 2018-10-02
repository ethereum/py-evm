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


.. autofunction:: eth.tools.builder.chain.chain_id


Initializing Chains
~~~~~~~~~~~~~~~~~~~

The following utilities are provided to assist with initializing a chain into
the genesis state.

.. autofunction:: eth.tools.builder.chain.genesis


Building Chains
~~~~~~~~~~~~~~~

The following utilities are provided to assist with building out chains of
blocks.


.. autofunction:: eth.tools.builder.chain.copy


.. autofunction:: eth.tools.builder.chain.import_block


.. autofunction:: eth.tools.builder.chain.import_blocks


.. autofunction:: eth.tools.builder.chain.mine_block


.. autofunction:: eth.tools.builder.chain.mine_blocks


.. autofunction:: eth.tools.builder.chain.chain_split


.. autofunction:: eth.tools.builder.chain.at_block_number
