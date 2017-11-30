Building Chains
====================


Using the Chain object
------------------------

A "single" blockchain is made by a series of different virtual machines
for different spans of blocks. For example, the Ethereum mainnet had
one virtual machine for blocks 0 till 1150000 (known as Frontier),
and another VM for blocks 1150000 till 1920000 (known as Homestead).

The :class:`~evm.chains.chain.Chain` object manages the series of fork rules,
after you define the VM ranges. For example, to set up a chain that would track
the mainnet Ethereum network until block 1920000, you could create this chain
class:

::

  from evm import constants, Chain
  from evm.vm.forks.frontier import FrontierVM
  from evm.vm.forks.homestead import HomesteadVM

  chain_class = Chain.configure(
    name='Test Chain',
    vm_configuration=(
      (constants.GENESIS_BLOCK_NUMBER, FrontierVM),
      (constants.HOMESTEAD_MAINNET_BLOCK, HomesteadVM),
    ),
  )

Then to initialize, you can start it up with an in-memory database:

::

  from evm.db.backends.memory import MemoryDB
  from evm.db.chain import BaseChainDB
  from evm.chains.mainnet import MAINNET_GENESIS_HEADER

  # start a fresh in-memory db
  chaindb = BaseChainDB(MemoryDB())

  # initialize a fresh chain
  chain = chain_class.from_genesis_header(chaindb, MAINNET_GENESIS_HEADER)
