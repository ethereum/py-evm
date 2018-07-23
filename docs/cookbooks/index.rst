Cookbooks
=========

The Cookbooks are collections of simple recipes that demonstrate good practices to accomplish
common tasks. The examples are usually short answers to simple "How do I..." questions that go
beyond simple API descriptions but also don't need a full guide to become clear.

.. _evm_cookbook:

EVM Cookbook
~~~~~~~~~~~~

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

  >>> from eth.db.backends.memory import MemoryDB
  >>> from eth.chains.mainnet import MAINNET_GENESIS_HEADER

  >>> # start a fresh in-memory db

  >>> # initialize a fresh chain
  >>> chain = chain_class.from_genesis_header(MemoryDB(), MAINNET_GENESIS_HEADER)
