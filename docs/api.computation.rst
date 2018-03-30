Computation
===========

.. class:: evm.vm.computation.BaseComputation


Configuration
-------------

Each `~evm.vm.computation.BaseComputation` class **must** be configured with the following:

- ``opcodes``: A mapping from the opcode integer value to the logic function for the opcode.
- ``_precompiles``: A mapping of contract address to the precompile function
  for execution of precompiled contracts.


Methods and Properties
----------------------


.. attribute:: is_origin_computation

    Returns ``True`` if this computation is the outermost computation at ``depth == 0``.


.. attribute:: is_success

    Returns ``True`` if the computation did not result in an error.

.. attribute:: is_error

    Returns ``True`` if the computation resulted in an error.

.. attribute:: should_burn_gas

    Returns ``True`` if the remaining gas should be burned.

.. attribute:: should_return_gas

    Returns ``True`` if the remaining gas should be returned.

.. attribute:: should_erase_return_data

    Returns ``True`` if the return data should be zerod out due to an error.

.. method:: prepare_child_message(gas, to, value, data, code, \*\*kwargs)

    Helper method for creating a child computation.

.. method:: extend_memory(start_position, size)

    Extends the size of the memory to be at minimum ``start_position + size``
    bytes in length.  Raises `evm.exceptions.OutOfGas` if there is not enough
    gas to pay for extending the memory.

.. method:: memory_write(start_position, size, value)

    Writes ``value`` to memory at ``start_position``.  Requires that ``len(value) == size``.

.. method:: memory_read(start_position, size)

    Reads and returns ``size`` bytes from memory starting at ``start_position``.

.. method:: consume_gas(amount, reason)

    Consumes ``amount`` of gas from the remaining gas.  Raises
    `evm.exceptions.OutOfGas` if there is not enough gas remaining.

.. method:: return_gas(amount)

    Returns ``amount`` of gas to the available gas pool.

.. method:: refund_gas(amount)

    Adds ``amount`` of gas to the pool of gas marked to be refunded.

.. method:: stack_pop(num_items=1, type_hint=None)

    Pops and returns a number of items equal to ``num_items`` from the stack.
    ``type_hint`` can be either ``'uint256'`` or ``'bytes'``.  The return value
    will be an ``int`` or ``bytes`` type depending on the value provided for
    the ``type_hint``.

    Raises `evm.exceptions.InsufficientStack` if there are not enough items on
    the stack.

.. method:: stack_push(value)

    Pushes ``value`` onto the stack.

    Raises `evm.exceptions.StackDepthLimit` if the stack is full.

.. method:: stack_swap(position)

    Swaps the item on the top of the stack with the item at ``position``.

.. method:: stack_dup(position)

    Duplicates the stack item at ``position`` and pushes it onto the stack.

.. attribute:: output

    The return value of the computation.

.. method:: apply_child_computation(self, child_msg)

    Applies the vm message ``child_msg`` as a child computation.

.. method:: generate_child_computation(cls, state, child_msg, transaction_context)

    STUB

.. method:: add_child_computation(self, child_computation)

    STUB

.. method:: register_account_for_deletion(self, beneficiary)

    STUB

.. method:: add_log_entry(self, account, topics, data)

    STUB

.. method:: get_accounts_for_deletion(self)

    STUB

.. method:: get_log_entries(self)

    STUB

.. method:: get_gas_refund(self)

    STUB

.. method:: get_gas_used(self)

    STUB

.. method:: get_gas_remaining(self)

    STUB

.. method:: state_db(self, read_only=False)

    STUB

.. method:: apply_message(self):

    STUB

.. method:: apply_create_message(self):

    STUB

.. method:: apply_computation(cls, state, message, transaction_context):

    STUB

.. attribute:: precompiles(self):

    STUB

.. method:: get_opcode_fn(self, opcodes, opcode):

    STUB
