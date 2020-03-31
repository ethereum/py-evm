Understanding the mining process
================================

From the :doc:`Cookbook </cookbook/index>` we can already learn how to
use the :class:`~eth.chains.base.Chain` class to create a single
blockchain as a combination of different virtual machines for different spans
of blocks.

In this guide we want to build up on that knowledge and look into the actual mining process.


.. note::

  Mining is an overloaded term and in fact the names of the mentioned APIs are subject to change.


Mining
------

The term *mining* can refer to different things depending on our point of view. Most of the time
when we read about *mining*, we talk about the process where several parties are *competing* to be
the first to create a new valid block and pass it on to the network.

In this guide, when we talk about the
:func:`~eth.chains.base.MiningChain.mine_block` API, we are only referring to
the part that creates, validates and sets a block as the new canonical head of
the chain but not necessarily as part of the mentioned competition to be the
first. In fact, the :func:`~eth.chains.base.MiningChain.mine_block` API is
internally also called when we import existing blocks that others created.

Mining an empty block
---------------------

Usually when we think about creating blocks we naturally think about adding transactions to the
block first because, after all, one primary use case for the Ethereum blockchain is to process
*transactions* which are wrapped in blocks.

For the sake of simplicity though, we'll mine an empty block as a first example (meaning the block
will not contain any transactions)

As a refresher, he's how we create a chain as demonstrated in the
:ref:`Using the chain object recipe<evm_cookbook_recipe_using_the_chain_object>` from the
cookbook.

::

  from eth.db.atomic import AtomicDB
  from eth.chains.mainnet import MAINNET_GENESIS_HEADER

  # increase the gas limit
  genesis_header = MAINNET_GENESIS_HEADER.copy(gas_limit=3141592)

  # initialize a fresh chain
  chain = chain_class.from_genesis_header(AtomicDB(), genesis_header)

Since we decided to not add any transactions to our block let's just call
:func:`~~eth.chains.base.MiningChain.mine_block` and see what happens.

::

  # initialize a fresh chain
  chain = chain_class.from_genesis_header(AtomicDB(), genesis_header)

  chain.mine_block()

Aw, snap! We're running into an exception at :func:`~eth.consensus.pow.check_pow`. Apparently we
are trying to add a block to the chain that doesn't qualify the Proof-of-Work (PoW) rules. The
error tells us precisely that the ``mix_hash`` of our block does not match the expected value.

.. code-block:: console

  Traceback (most recent call last):
    File "scripts/benchmark/run.py", line 111, in <module>
      run()
    File "scripts/benchmark/run.py", line 52, in run
      block = chain.mine_block()  #**pow_args
    File "/py-evm/eth/chains/base.py", line 545, in mine_block
      self.validate_block(mined_block)
    File "/py-evm/eth/chains/base.py", line 585, in validate_block
      self.validate_seal(block.header)
    File "/py-evm/eth/chains/base.py", line 622, in validate_seal
      header.mix_hash, header.nonce, header.difficulty)
    File "/py-evm/eth/consensus/pow.py", line 70, in check_pow
      encode_hex(mining_output[b'mix digest']), encode_hex(mix_hash)))

  eth.exceptions.ValidationError: mix hash mismatch;
  0x7a76bbf0c8d0e683fafa2d7cab27f601e19f35e7ecad7e1abb064b6f8f08fe21 !=
  0x0000000000000000000000000000000000000000000000000000000000000000

Let's lookup how :func:`~eth.consensus.pow.check_pow` is implemented.


.. literalinclude:: ../../eth/consensus/pow.py
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
:func:`~~eth.chains.base.MiningChain.mine_block` as seen below.


::

  chain.mine_block(nonce=valid_nonce, mix_hash=valid_mix_hash)

This call will work just fine assuming we are passing the correct ``nonce`` and ``mix_hash`` that
corresponds to the block getting mined.

Retrieving a valid nonce and mix hash
-------------------------------------


Now that we know we can call :func:`~~eth.chains.base.MiningChain.mine_block`
with the correct parameters to successfully add a block to our chain, let's
briefly go over an example that demonstrates how we can retrieve a matching
``nonce`` and ``mix_hash``.

.. note::

  Py-EVM currently doesn't offer a stable API for actual PoW mining. The following code is for
  demonstration purpose only.

Mining on the main ethereum chain is a competition done simultanously by many miners, hence the
*mining difficulty* is pretty high which means it will take a very long time to find the right
``nonce`` and ``mix_hash`` on commodity hardware. In order for us to have something that we can
tinker with on a regular laptop, we'll construct a test chain with the ``difficulty`` set to ``1``.

Let's start off by defining the ``GENESIS_PARAMS``.

::

  from eth import constants

  GENESIS_PARAMS = {
        'parent_hash': constants.GENESIS_PARENT_HASH,
        'uncles_hash': constants.EMPTY_UNCLE_HASH,
        'coinbase': constants.ZERO_ADDRESS,
        'transaction_root': constants.BLANK_ROOT_HASH,
        'receipt_root': constants.BLANK_ROOT_HASH,
        'difficulty': 1,
        'block_number': constants.GENESIS_BLOCK_NUMBER,
        'gas_limit': 3141592,
        'timestamp': 1514764800,
        'extra_data': constants.GENESIS_EXTRA_DATA,
        'nonce': constants.GENESIS_NONCE
    }

Next, we'll create the chain itself using the defined ``GENESIS_PARAMS`` and the latest
``ByzantiumVM``.

::

  from eth import MiningChain
  from eth.vm.forks.byzantium import ByzantiumVM
  from eth.db.backends.memory import AtomicDB


  klass = MiningChain.configure(
      __name__='TestChain',
      vm_configuration=(
          (constants.GENESIS_BLOCK_NUMBER, ByzantiumVM),
      ))
  chain = klass.from_genesis(AtomicDB(), GENESIS_PARAMS)


Now that we have the building blocks available, let's put it all together and mine a proper block!

::

    from eth.consensus.pow import mine_pow_nonce


    # We have to finalize the block first in order to be able read the
    # attributes that are important for the PoW algorithm
    block_result = chain.get_vm().finalize_block(chain.get_block())
    block = block_result.block

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

1. We call :func:`~eth.vm.base.VM.finalize_block` on the underlying VM in order to retrieve the
information that we need to calculate the ``nonce`` and the ``mix_hash``.

2. We then call :func:`~eth.consensus.pow.mine_pow_nonce` to retrieve the proper ``nonce`` and
``mix_hash`` that we need to mine the block and satisfy the validation.

3. Finally we call :func:`~eth.chain.base.MiningChain.mine_block` and pass
   along the ``nonce`` and the ``mix_hash``

.. note::

  The code above will essentially perform ``finalize_block`` twice.
  Keep in mind this code is for demonstration purpose only and that Py-EVM will provide a pluggable
  system in the future to allow PoW mining among other things.

Mining a block with transactions
--------------------------------

Now that we've learned the basics of how the mining process works, let's revisited our example and
add a transaction before we mine another block. There are a couple of concepts we need to dive into in
order to accomplish that goal.

Every transaction goes from a sender :class:`~eth_typing.misc.Address` to a receiver
:class:`~eth_typing.misc.Address`. Each transaction takes some computational power to get processed
that is measured in a unit called ``gas``.


In practice, we have to pay the miners to put our transaction in a block. However, there is no
*technical* reason why we have to pay for the computing power, but only an economical, i.e. in reality
we'll usually have trouble finding a miner who's willing to include a transaction that doesn't pay
for its computational costs.

In this example, however, **we are the miner** which means we are free to include any transactions
we like. In the spirit of this guide, let's start simple and create a transaction that sends zero
ether from one address to another address. Keep in mind that even if the value being transferred
is zero, there's still a computational cost for the processing but since we are the miner, we'll
mine it anyway even if no one is willing to pay for it!

Let's first setup the sender and receiver.

::

    from eth_keys import keys
    from eth_utils import decode_hex
    from eth_typing import Address

    SENDER_PRIVATE_KEY = keys.PrivateKey(
      decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8')
    )

    SENDER = Address(SENDER_PRIVATE_KEY.public_key.to_canonical_address())

    RECEIVER = Address(b'\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\x02')

One thing that strikes out here is that we only need the plain address for the receiver whereas for
the sender we are obtaining an address derived from the ``SENDER_PRIVATE_KEY``. That's because we
obviously can not send transactions from an address that we don't have the private key to sign it
for.

With sender and receiver prepared, let's create the actual transaction.

::

    vm = chain.get_vm()
    nonce = vm.state.get_nonce(SENDER)

    tx = vm.create_unsigned_transaction(
        nonce=nonce,
        gas_price=0,
        gas=100000,
        to=RECEIVER,
        value=0,
        data=b'',
    )

Every transaction needs a ``nonce`` not to be confused with the ``nonce`` that we previously
mined as part of the PoW algorithm. The *transaction nonce* serves as a counter to ensure
all transactions from one address are processed in order. We retrieve the current ``nonce``
by calling :func:`~eth.vm.base.VM.state.get_nonce(sender)`.

Once we have the ``nonce`` we can call :func:`~eth.vm.base.VM.create_unsigned_transaction` and
pass the ``nonce`` among the rest of the transaction attributes as key-value pairs.

* ``nonce`` - Number of transactions sent by the sender
* ``gas_price`` - Number of ``Wei`` to pay per unit of gas
* ``gas`` - Maximum amount of ``gas`` the transaction is allowed to consume before it gets rejected
* ``to`` - Address of transaction recipient
* ``value`` - Number of ``Wei`` to be transferred to the recipient

The last step we need to do before we can add the transaction to a block is to sign it with the
private key which is as simple as calling
:func:`~eth.rlp.transactions.BaseUnsignedTransaction.as_signed_transaction` with the
``SENDER_PRIVATE_KEY``.

::

    signed_tx = tx.as_signed_transaction(SENDER_PRIVATE_KEY)

Finally, we can call :func:`~eth.chains.base.MiningChain.apply_transaction` and pass along the
``signed_tx``.

::

    chain.apply_transaction(signed_tx)

What follows is the complete script that demonstrates how to mine a single block with one simple
zero value transfer transaction.

.. doctest::

  >>> from eth_keys import keys
  >>> from eth_utils import decode_hex
  >>> from eth_typing import Address
  >>> from eth import constants
  >>> from eth.chains.base import MiningChain
  >>> from eth.consensus.pow import mine_pow_nonce
  >>> from eth.vm.forks.byzantium import ByzantiumVM
  >>> from eth.db.atomic import AtomicDB


  >>> GENESIS_PARAMS = {
  ...     'parent_hash': constants.GENESIS_PARENT_HASH,
  ...     'uncles_hash': constants.EMPTY_UNCLE_HASH,
  ...     'coinbase': constants.ZERO_ADDRESS,
  ...     'transaction_root': constants.BLANK_ROOT_HASH,
  ...     'receipt_root': constants.BLANK_ROOT_HASH,
  ...     'difficulty': 1,
  ...     'block_number': constants.GENESIS_BLOCK_NUMBER,
  ...     'gas_limit': 3141592,
  ...     'timestamp': 1514764800,
  ...     'extra_data': constants.GENESIS_EXTRA_DATA,
  ...     'nonce': constants.GENESIS_NONCE
  ... }

  >>> SENDER_PRIVATE_KEY = keys.PrivateKey(
  ...     decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8')
  ... )

  >>> SENDER = Address(SENDER_PRIVATE_KEY.public_key.to_canonical_address())

  >>> RECEIVER = Address(b'\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\x02')

  >>> klass = MiningChain.configure(
  ...     __name__='TestChain',
  ...     vm_configuration=(
  ...         (constants.GENESIS_BLOCK_NUMBER, ByzantiumVM),
  ...     ))

  >>> chain = klass.from_genesis(AtomicDB(), GENESIS_PARAMS)
  >>> vm = chain.get_vm()

  >>> nonce = vm.state.get_nonce(SENDER)

  >>> tx = vm.create_unsigned_transaction(
  ...     nonce=nonce,
  ...     gas_price=0,
  ...     gas=100000,
  ...     to=RECEIVER,
  ...     value=0,
  ...     data=b'',
  ... )

  >>> signed_tx = tx.as_signed_transaction(SENDER_PRIVATE_KEY)

  >>> chain.apply_transaction(signed_tx)
  (<ByzantiumBlock(#Block #1...)
  >>> # We have to finalize the block first in order to be able read the
  >>> # attributes that are important for the PoW algorithm
  >>> block_result = chain.get_vm().finalize_block(chain.get_block())
  >>> block = block_result.block

  >>> # based on mining_hash, block number and difficulty we can perform
  >>> # the actual Proof of Work (PoW) mechanism to mine the correct
  >>> # nonce and mix_hash for this block
  >>> nonce, mix_hash = mine_pow_nonce(
  ...     block.number,
  ...     block.header.mining_hash,
  ...     block.header.difficulty
  ... )

  >>> chain.mine_block(mix_hash=mix_hash, nonce=nonce)
  <ByzantiumBlock(#Block #1-0x41f6..2913)>
