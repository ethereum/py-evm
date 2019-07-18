Cookbook
========

The Cookbook is a collection of simple recipes that demonstrate good practices to accomplish
common tasks. The examples are usually short answers to simple "How do I..." questions that go
beyond simple API descriptions but also don't need a full guide to become clear.


.. _evm_cookbook_recipe_using_the_chain_object:

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

  >>> from eth.db.atomic import AtomicDB
  >>> from eth.chains.mainnet import MAINNET_GENESIS_HEADER

  >>> # start a fresh in-memory db

  >>> # initialize a fresh chain
  >>> chain = chain_class.from_genesis_header(AtomicDB(), MAINNET_GENESIS_HEADER)

.. _evm_cookbook_recipe_creating_a_chain_with_custom_state:

Creating a chain with custom state
----------------------------------

While the previous recipe demos how to create a chain from an existing genesis header, we can
also create chains simply by specifing various genesis parameter as well as an optional genesis
state.

.. doctest::

  >>> from eth_keys import keys
  >>> from eth import constants
  >>> from eth.chains.mainnet import MainnetChain
  >>> from eth.db.atomic import AtomicDB
  >>> from eth_utils import to_wei, encode_hex



  >>> # Giving funds to some address
  >>> SOME_ADDRESS = b'\x85\x82\xa2\x89V\xb9%\x93M\x03\xdd\xb4Xu\xe1\x8e\x85\x93\x12\xc1'
  >>> GENESIS_STATE = {
  ...     SOME_ADDRESS: {
  ...         "balance": to_wei(10000, 'ether'),
  ...         "nonce": 0,
  ...         "code": b'',
  ...         "storage": {}
  ...     }
  ... }

  >>> GENESIS_PARAMS = {
  ...     'parent_hash': constants.GENESIS_PARENT_HASH,
  ...     'uncles_hash': constants.EMPTY_UNCLE_HASH,
  ...     'coinbase': constants.ZERO_ADDRESS,
  ...     'transaction_root': constants.BLANK_ROOT_HASH,
  ...     'receipt_root': constants.BLANK_ROOT_HASH,
  ...     'difficulty': constants.GENESIS_DIFFICULTY,
  ...     'block_number': constants.GENESIS_BLOCK_NUMBER,
  ...     'gas_limit': constants.GENESIS_GAS_LIMIT,
  ...     'extra_data': constants.GENESIS_EXTRA_DATA,
  ...     'nonce': constants.GENESIS_NONCE
  ... }

  >>> chain = MainnetChain.from_genesis(AtomicDB(), GENESIS_PARAMS, GENESIS_STATE)

.. _evm_cookbook_recipe_getting_the_balance_from_an_account:

Getting the balance from an account
-----------------------------------

Considering our previous example, we can get the balance of our pre-funded account as follows.

.. doctest::

  >>> current_vm = chain.get_vm()
  >>> state = current_vm.state
  >>> state.get_balance(SOME_ADDRESS)
  10000000000000000000000

.. _evm_cookbook_recipe_building_blocks_incrementally:

Building blocks incrementally
------------------------------

The default :class:`~eth.chains.chain.Chain` is stateless and thus does not keep a tip block open
that would allow us to incrementally build a block. However, we can import the 
:class:`~eth.chains.chain.MiningChain` which does allow exactly that.

.. doctest::

  >>> from eth.chains.base import MiningChain

Please check out the :doc:`Understanding the mining process
</guides/understanding_the_mining_process>` guide for a full example that demonstrates how 
to use the :class:`~eth.chains.chain.MiningChain`.
