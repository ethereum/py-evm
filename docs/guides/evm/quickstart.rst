Quickstart
====================

.. note::

  This quickstart is aspirational. The code examples may not work
  yet.


Installation
------------

.. code:: sh

  pip install py-evm


Sync and interact with the Ropsten chain
----------------------------------------

Currently we only provide a light client that will sync only block headers,
although it can fetch block bodies on demand. The easiest way to try it is by
running the lightchain_shell, which will run the LightPeerChain in the background
and let you use the python interpreter to interact with it:

.. code:: sh

  $ python -i -m eth.lightchain_shell -db /tmp/testnet.db


That will immediately give you a python shell, with a chain variable that you
can use even before it has finished syncing:

.. code:: python

  >>> chain.get_canonical_head()
  <BlockHeader #2200794 e3f9c6bb>

Some :class:`~p2p.lightchain.LightPeerChain` methods (e.g. those that need data
from block bodies) are coroutines that need to be executed by asyncio's event
loop, so for those we provide a helper that will schedule their execution and
wait for the result:

.. code:: python

  >>> wait_for_result(chain.get_canonical_block_by_number(42))
  <FrontierBlock(#Block #42)>


Accessing an existing chain database
------------------------------------

The :class:`~eth.chains.chain.Chain` object manages the series of fork rules
contained in every blockchain. It requires that you define the VM ranges.
Some pre-built chains are available for your convenience.
To access the Mainnet chain you can use:

.. code:: python

  from eth import MainnetChain
  from eth.chains.mainnet import MAINNET_GENESIS_HEADER
  from eth.db.backends.level import LevelDB
  from eth.db.chain import ChainDB

  # Read the previously saved chain database
  chaindb = ChainDB(LevelDB('/tmp/mainnet.db'))

  # Load the saved database into a mainnet chain object
  chain = MainnetChain(chaindb)


Then you can read data about the chain that you already downloaded.
For example:

.. code:: python

  highest_block_num = chain.get_canonical_head().block_number

  block1 = chain.get_canonical_block_by_number(1)
  assert block1.number == 1

  blockhash = block1.hash()
  vm = chain.get_vm()
  blockgas = vm.get_cumulative_gas_used(block1)

The methods available on the block are variable. They depend on what fork you're on.
The mainnet follows "Frontier" rules at the beginning, then Homestead, and so on.
To see block features for Frontier, see the API for
:class:`~eth.vm.forks.frontier.blocks.FrontierBlock`.
