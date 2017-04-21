import logging

from evm.logic.invalid import (
    InvalidOpcode,
)
from evm.validation import (
    validate_evm_block_ranges,
)

from evm.utils.ranges import (
    range_sort_fn,
    find_range,
)


class BaseEVM(object):
    """
    The EVM class is... TODO:
    """
    db = None

    block = None

    opcodes = None
    block_class = None

    def __init__(self, db, header):
        self.db = db
        self.header = header

        block_class = self.get_block_class()
        self.block = block_class(header=self.header, db=self.db)

    @classmethod
    def configure(cls,
                  name,
                  **overrides):
        for key in overrides:
            if not hasattr(cls, key):
                raise TypeError(
                    "The EVM.configure cannot set attributes that are not "
                    "already present on the base class.  The attribute `{0}` was "
                    "not found on the base class `{1}`".format(key, cls)
                )
        return type(name, (cls,), overrides)

    #
    # Logging
    #
    @property
    def logger(self):
        return logging.getLogger('evm.vm.evm.EVM.{0}'.format(self.__class__.__name__))

    #
    # Execution
    #
    def apply_transaction(self, transaction):
        """
        Execution of a transaction in the EVM.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def apply_create_message(self, message):
        """
        Execution of an EVM message to create a new contract.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def apply_message(self, message):
        """
        Execution of an EVM message.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def apply_computation(self, message):
        """
        Perform the computation that would be triggered by the EVM message.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Transactions
    #
    @classmethod
    def get_transaction_class(cls):
        """
        Return the class that this EVM uses for transactions.
        """
        return cls.get_block_class().get_transaction_class()

    def validate_transaction(self, transaction):
        """
        Perform evm-aware validation checks on the transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def create_transaction(self, *args, **kwargs):
        """
        Proxy for instantiating a transaction for this EVM.
        """
        return self.get_transaction_class()(*args, **kwargs)

    #
    # Blocks
    #
    block_class = None

    @classmethod
    def get_block_class(cls):
        """
        Return the class that this EVM uses for blocks.
        """
        if cls.block_class is None:
            raise AttributeError("No `block_class` has been set for this EVM")

        return cls.block_class

    @classmethod
    def initialize_block(cls, header):
        """
        Return the class that this EVM uses for transactions.
        """
        block_class = cls.get_block_class()
        return block_class(
            header=header,
            db=cls.db,
        )

    @classmethod
    def finalize_block(cls):
        raise NotImplementedError("TODO")

    #
    # EVM level DB operations.
    #
    @classmethod
    def get_block_hash(cls, block_number):
        """
        Return the block has for the requested block number.

        # TODO: is this the correct place for this API?
        """
        return cls.db.get_block_hash(block_number)

    #
    # Snapshot and Revert
    #
    def snapshot(self):
        """
        Perform a full snapshot of the current state of the EVM.

        TODO: This needs to do more than just snapshot the state_db but this is a start.
        """
        return self.block.state_db.snapshot()

    def revert(self, snapshot):
        """
        Revert the EVM to the state

        TODO: This needs to do more than just snapshot the state_db but this is a start.
        """
        return self.block.state_db.revert(snapshot)

    #
    # Opcode API
    #
    def get_opcode_fn(self, opcode):
        try:
            return self.opcodes[opcode]
        except KeyError:
            return InvalidOpcode(opcode)


class MetaEVM(object):
    db = None
    header = None

    ranges = None
    evms = None

    """
    TOOD: better name...
    The EVMChain combines multiple EVM classes into a single EVM.  Each sub-EVM

    Acknowledgement that this is not really a class but a function disguised as
    a class.  It is however easier to reason about in this format.
    """
    def __init__(self, db, header):
        self.db = db
        self.header = header

    @classmethod
    def configure(cls, name, evm_block_ranges):
        if not evm_block_ranges:
            raise TypeError("MetaEVM requires at least one set of EVM rules")

        if len(evm_block_ranges) == 1:
            # edge case for a single range.
            ranges = [evm_block_ranges[0][0]]
            evms = [evm_block_ranges[0][1]]
        else:
            raw_ranges, evms = zip(*evm_block_ranges)
            ranges = tuple(sorted(raw_ranges, key=range_sort_fn))

        validate_evm_block_ranges(ranges)

        evms = {
            range: evm
            for range, evm
            in evm_block_ranges
        }

        props = {
            'ranges': ranges,
            'evms': evms,
        }
        return type(name, (cls,), props)

    @classmethod
    def get_evm_class_for_block_number(self, block_number):
        range = find_range(self.ranges, block_number)
        evm_class = self.evms[range]
        return evm_class

    def get_evm(self):
        evm_class = self.get_evm_class_for_block_number(self.header.block_number)
        evm = evm_class(header=self.header, db=self.db)
        return evm

    #
    # Wrapper API around inner EVM classes
    #
    def apply_transaction(self, transaction):
        evm_class = self.get_evm_class_for_block_number(self.header.block_number)
        evm = evm_class(self.db, self.header)
        computation = evm.block.apply_transaction(evm, transaction)
        # icky mutation...
        self.header = evm.block.header
        return computation
