Creating Opcodes
================

An opcode is just a function which takes a :class:`~eth.vm.computation.BaseComputation`
instance as it's sole argument.  If an opcode function has a return value, this
value will be discarded during normal VM execution.

Here are some simple examples.

.. code-block:: python

    def noop(computation):
        """
        An opcode which does nothing (not even consume gas)
        """
        pass

    def burn_5_gas(computation):
        """
        An opcode which simply burns 5 gas
        """
        computation.consume_gas(5, reason='why not?')


The :func:`~eth.vm.opcode.as_opcode` helper
-------------------------------------------


While these examples are demonstrative of *simple* logic, opcodes will
traditionally have an intrinsic gas cost associated with them.  Py-EVM offers
an abstraction which allows for decoupling of gas consumption from opcode logic
which can be convenient for cases where an opcode's gas cost changes between
different VM rules but its logic remains constant.

.. py:function:: eth.vm.opcode.as_opcode(logic_fn, mnemonic, gas_cost)

    * The ``logic_fn`` argument should be a callable conforming to the opcode
      API, taking a `~eth.vm.computation.Computation` instance as its sole
      argument.
    * The ``mnemonic`` is a string such as ``'ADD'`` or ``'MUL'``.
    * The ``gas_cost`` is the gas cost to execute this opcode.

    The return value is a function which will consume the ``gas_cost`` prior to
    execution of the ``logic_fn``.


Usage of the :func:`~eth.vm.opcode.as_opcode` helper:


.. code-block:: python

    def custom_op(computation):
        ... # opcode logic here
    
    class ExampleComputation(BaseComputation):
        opcodes = {
            b'\x01': as_opcode(custom_op, 'CUSTOM_OP', 10),
        }


Opcodes as classes
------------------

Sometimes it may be helpful to share common logic between similar opcodes, or
the same opcode across multiple fork rules.  In these cases, implementing
opcodes as classes *may* be the right choice.  This is as simple as
implementing a ``__call__`` method on your class which conforms to the opcode
API, taking a single :class:`~eth.vm.computation.Computation` instance as the sole
argument.

.. code-block:: python

    class MyOpcode:
        def initial_logic(self, computation):
            ...

        def main_logic(self, computation):
            ...

        def cleanup_logic(self, computation):
            ...

        def __call__(self, computation):
            self.initial_logic(computation)
            self.main_logic(computation)
            self.cleanup_logic(computation)


With this pattern, the overall structure, as well as much of the logic can be
re-used while still allowing a mechanism for overriding individual sections of
the opcode logic.
