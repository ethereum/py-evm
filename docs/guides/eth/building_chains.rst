Building Chains
===============


Using the Chain object
----------------------

A "single" blockchain is made by a series of different virtual machines
for different spans of blocks. For example, the Ethereum mainnet had
one virtual machine for blocks 0 till 1150000 (known as Frontier),
and another VM for blocks 1150000 till 1920000 (known as Homestead).

The :class:`~eth.chains.chain.Chain` object manages the series of fork rules,
after you define the VM ranges. For example, to set up a chain that would track
the mainnet Ethereum network until block 1920000, you could create this chain
class:

.. doctest::

  >>> from eth import constants, Chain
  >>> from eth.vm.forks.frontier import FrontierVM
  >>> from eth.vm.forks.homestead import HomesteadVM
  >>> from eth.chains.mainnet import HOMESTEAD_MAINNET_BLOCK

  >>> chain_class = Chain.configure(
  ...     __name__='Test Chain',
  ...     vm_configuration=(
  ...         (constants.GENESIS_BLOCK_NUMBER, FrontierVM),
  ...         (HOMESTEAD_MAINNET_BLOCK, HomesteadVM),
  ...     ),
  ... )

Then to initialize, you can start it up with an in-memory database:

.. doctest::

  >>> from eth.db.backends.memory import MemoryDB
  >>> from eth.chains.mainnet import MAINNET_GENESIS_HEADER

  >>> # start a fresh in-memory db

  >>> # initialize a fresh chain
  >>> chain = chain_class.from_genesis_header(MemoryDB(), MAINNET_GENESIS_HEADER)


Using the LightPeerChain object
-------------------------------

The :class:`~p2p.lightchain.LightPeerChain` is like a Chain but it will also
connect to remote peers and fetch new :class:`~eth.rlp.headers.BlockHeader`
objects as they are announced on the network. As such, it must first be
configured with a `vm_configuration` and a `network_id`:

::

  from eth.chains.mainnet import MAINNET_VM_CONFIGURATION, MAINNET_NETWORK_ID
  from p2p import ecies
  from p2p.lightchain import LightPeerChain
  from p2p.peer import LESPeer, PeerPool

  DemoLightPeerChain = LightPeerChain.configure(
      __name__='Demo LightPeerChain',
      vm_configuration=MAINNET_VM_CONFIGURATION,
      network_id=MAINNET_NETWORK_ID,
  )


In order for it to connect to other peers in the network and fetch new
headers, you should give it a `privkey` and tell `asyncio` to execute
its `run()` method:

::

  import asyncio
  from eth.db.backends.memory import MemoryDB
  from eth.db.header import HeaderDB
  from eth.chains.mainnet import

  # start a fresh in-memory db
  base_db = MemoryDB()
  headerdb = HeaderDB(base_db)

  peer_pool = PeerPool(LESPeer, headerdb, MAINNET_NETWORK_ID, ecies.generate_privkey())

  chain = DemoLightPeerChain.from_genesis_header(base_db, MAINNET_GENESIS_HEADER, peer_pool)
  loop = asyncio.get_event_loop()
  loop.run_until_complete(chain.run())

