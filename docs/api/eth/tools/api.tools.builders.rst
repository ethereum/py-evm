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

.. automodule:: eth.tools.builder.chain
  :noindex:
  :members: fork_at,
            dao_fork_at,
            disable_dao_fork,
            enable_pow_mining,
            disable_pow_check,
            name


Initializing Chains
~~~~~~~~~~~~~~~~~~~

The following utilities are provided to assist with initializing a chain into
the genesis state.

.. automodule:: eth.tools.builder.chain
  :noindex:
  :members: genesis


Building Chains
~~~~~~~~~~~~~~~

The following utilities are provided to assist with building out chains of
blocks.

.. automodule:: eth.tools.builder.chain
  :noindex:
  :members: copy,
            import_block,
            import_blocks,
            mine_block,
            mine_blocks,
            chain_split,
            at_block_number
