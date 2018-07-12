Architecture
============

The primary use case for Py-EVM is supporting the public Ethereum blockchain.

However, it is architected with a strong focus on configurability and
extensibility.  Use of Py-EVM for alternate use cases such as private chains,
consortium chains, or even chains with fundamentally different VM semantics
should be possible without any changes to the core library.

The following abstractions are used to represent the full consensus rules for a
Py-EVM based blockchain.

- Chain: High level API for interacting with the blockchain.
- VM: High level API for a single fork within a Chain
- VMState: The current state of the VM, transaction execution logic and the state transition function.
- Message: Representation of the portion of the transaction which is relevant to VM execution.
- Computation: The computational state and result of VM execution.
- Opcode: The logic for a single opcode.


The Chain
---------

The term **Chain** is used to encapsulate:

- The state transition function (e.g. VM opcodes and execution logic)
- Protocol rules (e.g. block rewards, header rewards, difficulty calculations, transaction execution)
- The chain data (e.g. **Headers**, **Blocks**, **Transactions** and **Receipts**)
- The state data (e.g. **balance**, **nonce**, **code** and **storage**)
- The chain state (e.g. tracking the chain head, canonical blocks)

.. note:: While a chain is used to *wrap* these concepts, many of them are actually defined at lower layers such as the underlying **Virtual Machines**.

The ``Chain`` object itself is largely an interface and orchestration layer.
Most of the ``Chain`` APIs merely serving as a passthrough to the appropriate
``VM``.

A chain has one or more underlying **Virtual Machines** or VMs.  The chain
contains a mapping which defines which VM should be active for which blocks.

The chain for the public mainnet Ethereum blockchain would have a separate VM defined
for each fork ruleset (e.g. **Frontier**, **Homestead**, **Tangerine Whistle**,
**Spurious Dragon**, **Byzantium**).


The VM
------

The term **VM** is used to encapsulate:

- The state transition function for a single fork ruleset.
- Orchestration logic for transaction execution.
- Block construction and validation.
- Chain data storage and retrieval APIs

The ``VM`` object loosely mirrors many of the Chain APIs for retrieval of chain
state such as blocks, headers, transactions and receipts.  It is also
responsible for block level protocol logic such as block creation and
validation.


The VMState
-----------

The term **VMState** is used to encapsulate:

- Execution context for the VM (e.g. ``coinbase`` or ``gas_limit``)
- The state root defining the current VM state.
- Some block validation


The Message
-----------

The term **Message** comes from the yellow paper.  It encapsulates the
information from the transaction needed to initiate the outermost layer of VM
execution.

- Parameters like ``sender``, ``value``, ``to``

The message can be thought of as the VM's internal representation of a
transaction.


The Computation
---------------

The term **Computation** is used to encapsulate:

- The computational state during VM execution (e.g. memory, stack, gas metering)
- The computational results of VM execution (e.g. return data, gas consumption and refunds, execution errors)
  
This abstraction is the interface through which opcode logic is implemented.


The Opcode
----------

The term **Opcode** is used to encapsulate:

- A single instruction within the VM such as the ``ADD`` or ``MUL`` opcodes.

Opcodes are implemented as TODO
