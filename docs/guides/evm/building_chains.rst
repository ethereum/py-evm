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
  from evm.tools.chain import generate_vms_by_range
  from evm.vm.forks.frontier import FrontierVM
  from evm.vm.forks.homestead import HomesteadVM
  from evm.chains.mainnet import HOMESTEAD_MAINNET_BLOCK

  chain_class = Chain.configure(
      __name__='Test Chain',
      vms_by_range=generate_vms_by_range((
          (constants.GENESIS_BLOCK_NUMBER, FrontierVM),
          (HOMESTEAD_MAINNET_BLOCK, HomesteadVM),
      )),
  )

Then to initialize, you can start it up with an in-memory database:

::

  from evm.db.backends.memory import MemoryDB
  from evm.db.chain import ChainDB
  from evm.chains.mainnet import MAINNET_GENESIS_HEADER

  # start a fresh in-memory db
  chaindb = ChainDB(MemoryDB())

  # initialize a fresh chain
  chain = chain_class.from_genesis_header(chaindb, MAINNET_GENESIS_HEADER)


Using the LightChain object
---------------------------

The :class:`~p2p.lightchain.LightChain` is like a Chain but it will also
connect to remote peers and fetch new :class:`~evm.rlp.headers.BlockHeader` s
as they are announced on the network. As such, it must first be configured
with a vm_configuration, but it also requires a network_id and privkey:

::

  from evm.chains.mainnet import MAINNET_VM_CONFIGURATION, MAINNET_NETWORK_ID
  from p2p import ecies
  from p2p.lightchain import LightChain
  from p2p.peer import LESPeer, PeerPool

  DemoLightChain = LightChain.configure(
      __name__='Demo LightChain',
      vms_by_range=generate_vms_by_range(MAINNET_VM_CONFIGURATION),
      network_id=MAINNET_NETWORK_ID,
  )


And in order for it to connect to other peers in the network and fetch new
headers, you should tell asyncio to execute its run() method:

::

  import asyncio
  from evm.db.backends.memory import MemoryDB
  from evm.db.chain import ChainDB
  from evm.chains.mainnet import 

  # start a fresh in-memory db
  chaindb = ChainDB(MemoryDB())

  peer_pool = PeerPool(LESPeer, chaindb, MAINNET_NETWORK_ID, ecies.generate_privkey())

  chain = DemoLightChain.from_genesis_header(chaindb, MAINNET_GENESIS_HEADER, peer_pool)
  loop = asyncio.get_event_loop()
  loop.run_until_complete(chain.run())

