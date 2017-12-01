Quickstart
====================

.. note::

  This quickstart is aspirational. The code examples may not work
  yet.


Installation
------------

.. code:: sh

  pip install py-evm


Syncing with Mainnet
---------------------

Run the peer for a little while, saving the blockchain to a file of your chioce:

.. code:: sh

  $ python -m evm.p2p.peer --db /tmp/mychain.db --mainnet
  
After syncing some blocks, you can close out the process
to explore the chain directly with py-evm.

Accessing Mainnet
--------------------

The :class:`~evm.chains.chain.Chain` object manages the series of fork rules
contained in every blockchain. It requires that you define the VM ranges.
Some pre-built chains are available for your convenience.
To access the Mainnet chain you can use:

::

  from evm import MainnetChain
  from evm.chains.mainnet import MAINNET_GENESIS_HEADER
  from evm.db.backends.level import LevelDB
  from evm.db.chain import BaseChainDB

  # Read the previously saved chain database
  chaindb = BaseChainDB(LevelDB('/tmp/mychain.db'))

  # Load the saved database into a mainnet chain object
  chain = MainnetChain(chaindb)


Then you can read data about the chain that you already downloaded.
For example:

::

  highest_block_num = chain.get_canonical_head().block_number

  block1 = chain.get_canonical_block_by_number(1)
  assert block1.number() == 1

  blockhash = block1.hash()
  blockgas = block1.get_cumulative_gas_used()

The methods available on the block are variable. They depend on what fork you're on.
The mainnet follows "Frontier" rules at the beginning, then Homestead, and so on.
To see block features for Frontier, see the API for
:class:`~evm.vm.forks.frontier.blocks.FrontierBlock`.
