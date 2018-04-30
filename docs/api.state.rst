State
=====

.. class:: evm.vm.state.State


The `~evm.vm.state.State` class encapsulates all of the various moving parts
related to state of the VM during execution.

Each `~evm.vm.base.BaseVM` class must be configured with a subclass of the
`~evm.vm.state.State`.

Configuration
-------------

Each `~evm.vm.state.State` class is expected to have the following properties
configured.

- ``block_class``: The `~evm.rlp.blocks.Block` class for blocks in this VM ruleset.
- ``computation_class``: The `~evm.vm.computation.BaseComputation` class for vm
  execution.
- ``transaction_context_class``: The
  `~evm.vm.transaction_context.TransactionContext` class for vm execution.


Methods and Properties
----------------------

.. attribute:: coinbase

    Returns the current ``coinbase`` from the current :attr:`execution_context`

.. attribute:: timestamp

    Returns the current ``timestamp`` from the current :attr:`execution_context`

.. attribute:: block_number

    Returns the current ``block_number`` from the current :attr:`execution_context`


.. attribute:: difficulty()

    Returns the current ``difficulty`` from the current :attr:`execution_context`

.. attribute:: gas_limit()

    Returns the current ``gas_limit`` from the current :attr:`transaction_context`

.. attribute:: gas_used

    Returns the current ``gas_used`` from the current block.


.. attribute:: read_only_account_db

    Returns a read-only version of the account database.


.. method:: mutable_account_db()

    Returns the account database.


.. method:: account_db(read_only=False)

    Returns the account database.

    .. attention::

        This **must** be used as a context manager
        to ensure that modifications to the state root are correctly tracked.


.. method:: set_state_root(state_root)

    Update the current state root.


.. method:: snapshot()

    Take a snapshot which can later be used to roll back an vm changes to the
    point of the snapshot.

.. method:: revert(snapshot)

    Revert the state back to the snaapshot.

.. method:: commit(snapshot)

    Commits changes to the state database.  This discards any checkpoints which
    were taken **after** the ``snapshot``.  """

.. method:: is_key_exists(key)

    Return ``True`` or ``False`` for whether the given key is in the underlying database.

.. method:: get_ancestor_hash(block_number)

    Return the hash for the ancestor block with number ``block_number``.
    Returns the empty bytestring ``b''`` if the block number is outside of the
    range of available block numbers (typically the last 255 blocks).

.. method:: get_computation(message, transaction_context)

    Returns a `~evm.vm.computation.BaseComputation` instance which is ready to
    be executed.


.. method:: apply_transaction( transaction, block):

    Applies the given ``transaction`` within the current ``block``.  Used for
    incrementalling building blocks.

.. method:: add_transaction(transaction, computation, block)

    Adds the given ``transaction`` and completed ``computation`` to the given block.

.. method:: add_receipt(receipt)

    Adds the given ``receipt`` to the current block.


.. method:: make_receipt(transaction, computation)

    Creates and returns a receipt for the given transaction and completed computation.

.. method:: finalize_block(block)

    Perform any finalization steps (typically for things like awarding the block mining reward).

.. method:: get_block_reward():

    Return the amount in **wei** that should be given to a miner as a reward
    for this block.

.. method:: get_uncle_reward(block_number, uncle):

    Return the reward which should be given to the miner of the given `uncle`.

.. method:: get_nephew_reward(cls):

    Return the reward which should be given to the miner of the given `nephew`.
