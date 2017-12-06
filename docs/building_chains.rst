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


Using the LightChain object
---------------------------

The :class:`~evm.p2p.lightchain.LightChain` is like a Chain but it will also
connect to remote peers and fetch new :class:`~evm.rlp.headers.BlockHeader` s
as they are announced on the network. As such, it must first be configured
with a vm_configuration, but it also requires a network_id and privkey:

::

  from evm.chains.mainnet import MAINNET_VM_CONFIGURATION, MAINNET_NETWORK_ID
  from evm.p2p import ecies
  from evm.p2p.lightchain import LightChain

  DemoLightChain = LightChain.configure(
      name='Demo LightChain',
      privkey=ecies.generate_privkey(),
      vm_configuration=MAINNET_VM_CONFIGURATION,
      network_id=MAINNET_NETWORK_ID,
  )


And in order for it to connect to other peers in the network and fetch new
headers, you should tell asyncio to execute its run() method:

::

  import asyncio
  from evm.db.backends.memory import MemoryDB
  from evm.db.chain import BaseChainDB
  from evm.chains.mainnet import MAINNET_GENESIS_HEADER

  chain = DemoLightChain.from_genesis_header(BaseChainDB(MemoryDB()), MAINNET_GENESIS_HEADER)
  loop = asyncio.get_event_loop()
  loop.run_until_complete(chain.run())

