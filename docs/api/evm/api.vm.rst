Virtual Machine
===============

.. class:: evm.vm.computation.BaseComputation


Each `~evm.vm.base.BaseVM` class represents a single ruleset for the EVM (e.g. Frontier, Homestead, Spurious Dragon, etc).


Configuration
-------------

Each `~evm.vm.base.BaseVM` class is expected to have the following properties
configured.

- ``_state_class``: The `~evm.vm.state.State` class used by this VM for execution.


Properties and Methods
----------------------

.. method:: apply_transaction(transaction)

    Wrapper around the underlying
    :method:`~evm.vm.state.State.apply_transaction` method with some extra
    orchestration logic.

.. method:: execute_bytecode(origin, gas_price, gas, to, sender, value, data, code, code_address=None)

    API for execution of raw bytecode in the context of the current state of
    the virtual machine.

.. method:: import_block(block)

    Imports the given block to the chain.

.. method:: mine_block(TODO_HEADER_PARAMS)

    Mine the current block.

.. method:: pack_block(, block, TODO_HEADER_PARAMS)

    Prepare a block to be mined.

.. method:: validate_block(block)

    Run validation on the given block.

.. method:: validate_uncle(block, uncle)

    Run validation on the given uncle in the context of the given block.

.. classmethod:: get_transaction_class():

    Return the class that this VM uses for transactions.

.. method:: get_pending_transaction(transaction_hash)

    Return a transaction which is *pending* in the currently unmined tip block.

.. method:: create_transaction(TODO_TRANSACTION_PARAMS)

    Helper method for instantiating an instance of a signed transaction for
    this VM.

.. method:: create_unsigned_transaction(TODO_TRANSACTION_PARAMS)


    Helper method for instantiating an instance of a unsigned transaction for
    this VM.

.. classmethod:: get_block_class():

    Return the `~evm.rlp.blocks.Block` class that this VM uses for blocks.

.. classmethod:: get_block_by_header(block_header, db):

    Lookup and return the block for the given header.

.. classmethod:: get_prev_hashes(last_block_hash, db):

    Returns the block hashes for the previous 255 blocks.

.. attribute:: previous_hashes

    Shortcut for retrieving the previous 255 block hashes.

.. method:: get_cumulative_gas_used(block)

    Returns the current amount of gas used within the given block.

.. classmethod:: create_header_from_parent(parent_header, TODO_HEADER_PARAMS):

    Helper for creating a new header which is the child of ``parent_header``.

.. method:: configure_header(TODO_HEADER_PARAMS)

    Updates the header for the currently unmined tip block for this VM.

.. method:: compute_difficulty(cls, parent_header, timestamp):

    TODO
