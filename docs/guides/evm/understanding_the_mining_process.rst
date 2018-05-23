Understanding the mining process
================================

In the `Building Chains Guide <building_chains>`_ we already learned how to use the
:class:`~evm.chains.base.Chain` class to create a single blockchain as a combination of different
virtual machines for different spans of blocks.

In this guide we want to build up on that knowledge and look into the actual mining process.


.. note::

  Mining is an overloaded term and in fact the names of the mentioned APIs are subject to change.


Mining
------

The term *mining* can refer to different things depending on our point of view. Most of the time
when we read about *mining*, we talk about the process where several parties are *competing* to be
the first to create a new valid block and pass it on to the network.

In this guide, when we talk about the :func:`~evm.chains.base.Chain.mine_block` API, we are only
referring to the part that creates, validates and sets a block as the new canonical head of the
chain but not necessarily as part of the mentioned competition to be the first. In fact, the
:func:`~evm.chains.base.Chain.mine_block` API is internally also called when we import existing
blocks that others created.

Mining an empty block
---------------------

Usually when we think about creating blocks we naturally think about adding transactions to the
block first because, after all, one primary use case for the Ethereum blockchain is to process
*transactions* which are wrapped in blocks.

For the sake of simplicity though, we'll mine an empty block as a first example (meaning the block
will not contain any transactions)

As a refresher, he's where we left of as part of the `Building Chains Guide <building_chains>`_.

::

  from evm.db.backends.memory import MemoryDB
  from evm.chains.mainnet import MAINNET_GENESIS_HEADER

  # initialize a fresh chain
  chain = chain_class.from_genesis_header(MemoryDB(), MAINNET_GENESIS_HEADER)

Since we decided to not add any transactions to our block let's just call
:func:`~~evm.chains.base.Chain.mine_block` and see what happens.

::

  # initialize a fresh chain
  chain = chain_class.from_genesis_header(MemoryDB(), MAINNET_GENESIS_HEADER)

  chain.mine_block()

Aw, snap! We're running into an exception at :func:`~evm.consensus.pow.check_pow`. Apparently we
are trying to add a block to the chain that doesn't qualify the Proof-of-Work (PoW) rules. The
error tells us precisely that the ``mix_hash`` of our block does not match the expected value.

.. code-block:: console

  Traceback (most recent call last):
    File "scripts/benchmark/run.py", line 111, in <module>
      run()
    File "scripts/benchmark/run.py", line 52, in run
      block = chain.mine_block()  #**pow_args
    File "/py-evm/evm/chains/base.py", line 545, in mine_block
      self.validate_block(mined_block)
    File "/py-evm/evm/chains/base.py", line 585, in validate_block
      self.validate_seal(block.header)
    File "/py-evm/evm/chains/base.py", line 622, in validate_seal
      header.mix_hash, header.nonce, header.difficulty)
    File "/py-evm/evm/consensus/pow.py", line 70, in check_pow
      encode_hex(mining_output[b'mix digest']), encode_hex(mix_hash)))

  evm.exceptions.ValidationError: mix hash mismatch;
  0x7a76bbf0c8d0e683fafa2d7cab27f601e19f35e7ecad7e1abb064b6f8f08fe21 !=
  0x0000000000000000000000000000000000000000000000000000000000000000

Let's lookup how :func:`~evm.consensus.pow.check_pow` is implemented.


.. literalinclude:: ../../../evm/consensus/pow.py
   :language: python
   :pyobject: check_pow

Just by looking at the signature of that function we can see that validating the PoW is based on
the following parameters:

* ``block_number`` - the number of the given block
* ``difficulty`` - the difficulty of the PoW algorithm
* ``mining_hash`` - hash of the mining header
* ``mix_hash`` - together with the ``nonce`` forms the actual proof
* ``nonce`` - together with the ``mix_hash`` forms the actual proof



The PoW algorithm checks that all these parameters match correctly, ensuring that only valid blocks
can be added to the chain.

In order to produce a valid block, we have to set the correct ``mix_hash`` and ``nonce`` in the
header. We can pass these as key-value pairs when we call
:func:`~~evm.chains.base.Chain.mine_block` as seen below.


::

  chain.mine_block(nonce=valid_nonce, mix_hash=valid_mix_hash)

This call will work just fine assuming we are passing the correct ``nonce`` and ``mix_hash`` that
corresponds to the block getting mined.

Retrieving a valid nonce and mix hash
-------------------------------------


Now that we know we can call :func:`~~evm.chains.base.Chain.mine_block` with the correct parameters
to successfully add a block to our chain, let's briefly go over an example that demonstrates how we
can retrieve a matching ``nonce`` and ``mix_hash``.

.. note::

  Py-EVM currently doesn't offer a stable API for actual PoW mining. The following code is for
  demonstration purpose only.

Mining on the main ethereum chain is a competition done simultanously by many miners, hence the
*mining difficulty* is pretty high which means it will take a very long time to find the right
``nonce`` and ``mix_hash`` on commodity hardware. In order for us to have something that we can
tinker with on a regular laptop, we'll construct a test chain with the ``difficulty`` set to ``1``.

Let's start off by defining the ``GENESIS_PARAMS``.

::

  from evm import constants

  GENESIS_PARAMS = {
        'parent_hash': constants.GENESIS_PARENT_HASH,
        'uncles_hash': constants.EMPTY_UNCLE_HASH,
        'coinbase': constants.ZERO_ADDRESS,
        'transaction_root': constants.BLANK_ROOT_HASH,
        'receipt_root': constants.BLANK_ROOT_HASH,
        'difficulty': 1,
        'block_number': constants.GENESIS_BLOCK_NUMBER,
        'gas_limit': constants.GENESIS_GAS_LIMIT,
        'timestamp': 1514764800,
        'extra_data': constants.GENESIS_EXTRA_DATA,
        'nonce': constants.GENESIS_NONCE
    }

Next, we'll create the chain itself using the defined ``GENESIS_PARAMS`` and the latest
``ByzantiumVM``.

::

  from evm import Chain
  from evm.vm.forks.byzantium import ByzantiumVM
  from evm.db.backends.memory import MemoryDB


  klass = Chain.configure(
      __name__='TestChain',
      vm_configuration=(
          (constants.GENESIS_BLOCK_NUMBER, ByzantiumVM),
      ))
  chain = klass.from_genesis(MemoryDB(), GENESIS_PARAMS)


Now that we have the building blocks available, let's put it all together and mine a proper block!

::

    from evm.consensus.pow import mine_pow_nonce


    # We have to finalize the block first in order to be able read the
    # attributes that are important for the PoW algorithm
    block = chain.get_vm().finalize_block(chain.get_block())

    # based on mining_hash, block number and difficulty we can perform
    # the actual Proof of Work (PoW) mechanism to mine the correct
    # nonce and mix_hash for this block
    nonce, mix_hash = mine_pow_nonce(
        block.number,
        block.header.mining_hash,
        block.header.difficulty)

    block = chain.mine_block(mix_hash=mix_hash, nonce=nonce)

::

    >>> print(block)
    Block #1

Let's take a moment to fully understand what this code does.

1. We call :func:`~evm.vm.base.VM.finalize_block` on the underlying VM in order to retrieve the
information that we need to calculate the ``nonce`` and the ``mix_hash``.

2. We then call :func:`~evm.consensus.pow.mine_pow_nonce` to retrieve the proper ``nonce`` and
``mix_hash`` that we need to mine the block and satisfy the validation.

3. Finally we call :func:`~evm.chain.base.Chain.mine_block` and pass along the ``nonce`` and the
``mix_hash``

.. note::

  The code above will essentially perform ``finalize_block`` twice.
  Keep in mind this code is for demonstration purpose only and that Py-EVM will provide a pluggable
  system in the future to allow PoW mining among other things.