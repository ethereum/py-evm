import itertools
from types import TracebackType
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)

from eth.vm.computation.base_computation import (
    BaseComputation, NO_RESULT,
)
from eth_typing import (
    Address,
)
from eth_utils import (
    encode_hex,
    get_extended_debug_logger,
)

from eth.abc import (
    MessageAPI,
    MessageComputationAPI,
    StateAPI,
    TransactionContextAPI,
)
from eth.exceptions import (
    Halt,
    VMError,
)
from eth.typing import (
    BytesOrView,
)
from eth.validation import (
    validate_canonical_address,
    validate_is_bytes,
    validate_uint256,
)
from eth.vm.code_stream import (
    CodeStream,
)
from eth.vm.gas_meter import (
    GasMeter,
)
from eth.vm.logic.invalid import (
    InvalidOpcode,
)
from eth.vm.message import (
    Message,
)


class MessageComputation(BaseComputation, MessageComputationAPI):
    """
    A class for executing message computations.
    """

    logger = get_extended_debug_logger("eth.vm.computation.MessageComputation")

    msg: MessageAPI = None
    transaction_context: TransactionContextAPI = None
    children: List[MessageComputationAPI] = None
    accounts_to_delete: Dict[Address, Address] = None

    _log_entries: List[Tuple[int, Address, Tuple[int, ...], bytes]] = None

    def __init__(
        self,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
    ) -> None:
        super().__init__(state)

        self.msg = message
        self.transaction_context = transaction_context
        self.code = CodeStream(message.code)
        self._gas_meter = self._configure_gas_meter()

        self.children = []
        self.accounts_to_delete = {}
        self._log_entries = []

    def _configure_gas_meter(self) -> GasMeter:
        return GasMeter(self.msg.gas)

    # -- class methods -- #
    @classmethod
    def apply_message(
        cls,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
    ) -> MessageComputationAPI:
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    def apply_create_message(
        cls,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
    ) -> MessageComputationAPI:
        raise NotImplementedError("Must be implemented by subclasses")

    # -- convenience -- #
    @property
    def is_origin_computation(self) -> bool:
        return self.msg.sender == self.transaction_context.origin

    # -- runtime operations -- #
    def prepare_child_message(
        self,
        gas: int,
        to: Address,
        value: int,
        data: BytesOrView,
        code: bytes,
        **kwargs: Any,
    ) -> MessageAPI:
        kwargs.setdefault('sender', self.msg.storage_address)

        child_message = Message(
            gas=gas,
            to=to,
            value=value,
            data=data,
            code=code,
            depth=self.msg.depth + 1,
            **kwargs
        )
        return child_message

    def apply_child_message_computation(
        self,
        child_msg: MessageAPI,
    ) -> MessageComputationAPI:
        child_computation = self.generate_child_message_computation(child_msg)
        self.add_child_message_computation(child_computation)
        return child_computation

    def generate_child_message_computation(
        self,
        child_msg: MessageAPI,
    ) -> MessageComputationAPI:
        if child_msg.is_create:
            child_computation = self.apply_create_message(
                self.state,
                child_msg,
                self.transaction_context,
            )
        else:
            child_computation = self.apply_message(
                self.state,
                child_msg,
                self.transaction_context,
            )
        return child_computation

    def add_child_message_computation(
        self,
        child_message_computation: MessageComputationAPI,
    ) -> None:
        if child_message_computation.is_error:
            if child_message_computation.msg.is_create:
                self.return_data = child_message_computation.output
            elif child_message_computation.should_burn_gas:
                self.return_data = b''
            else:
                self.return_data = child_message_computation.output
        else:
            if child_message_computation.msg.is_create:
                self.return_data = b''
            else:
                self.return_data = child_message_computation.output
        self.children.append(child_message_computation)

    # -- gas consumption -- #
    def get_gas_refund(self) -> int:
        if self.is_error:
            return 0
        else:
            return (
                self._gas_meter.gas_refunded
                + sum(c.get_gas_refund() for c in self.children)
            )

    # -- account management -- #
    def register_account_for_deletion(self, beneficiary: Address) -> None:
        # SELFDESTRUCT

        validate_canonical_address(
            beneficiary,
            title="Self destruct beneficiary address",
        )

        if self.msg.storage_address in self.accounts_to_delete:
            raise ValueError(
                "Invariant.  Should be impossible for an account to be "
                "registered for deletion multiple times"
            )
        self.accounts_to_delete[self.msg.storage_address] = beneficiary

    def get_accounts_for_deletion(self) -> Tuple[Tuple[Address, Address], ...]:
        # SELFDESTRUCT

        if self.is_error:
            return ()
        else:
            return tuple(dict(itertools.chain(
                self.accounts_to_delete.items(),
                *(child.get_accounts_for_deletion() for child in self.children)
            )).items())

    # -- EVM logging -- #
    def add_log_entry(
        self,
        account: Address,
        topics: Tuple[int, ...],
        data: bytes,
    ) -> None:
        validate_canonical_address(account, title="Log entry address")
        for topic in topics:
            validate_uint256(topic, title="Log entry topic")
        validate_is_bytes(data, title="Log entry data")
        self._log_entries.append(
            (self.transaction_context.get_next_log_counter(), account, topics, data))

    def get_raw_log_entries(self) -> Tuple[
        Tuple[int, bytes, Tuple[int, ...], bytes], ...
    ]:
        if self.is_error:
            return ()
        else:
            return tuple(sorted(itertools.chain(
                self._log_entries,
                *(child.get_raw_log_entries() for child in self.children)
            )))

    def get_log_entries(self) -> Tuple[Tuple[bytes, Tuple[int, ...], bytes], ...]:
        return tuple(log[1:] for log in self.get_raw_log_entries())

    # -- state transition -- #
    @classmethod
    def apply_computation(
        cls,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
    ) -> MessageComputationAPI:

        with cls(state, message, transaction_context) as computation:
            if message.is_create and computation.is_origin_computation:
                # If computation is from a create transaction, consume initcode gas if
                # >= Shanghai. CREATE and CREATE2 are handled in the opcode
                # implementations.
                cls.consume_initcode_gas_cost(computation)

            # Early exit on pre-compiles
            precompile = computation.precompiles.get(
                message.code_address, NO_RESULT
            )
            if precompile is not NO_RESULT:
                precompile(computation)
                return computation

            show_debug2 = computation.logger.show_debug2

            opcode_lookup = computation.opcodes
            for opcode in computation.code:
                try:
                    opcode_fn = opcode_lookup[opcode]
                except KeyError:
                    opcode_fn = InvalidOpcode(opcode)

                if show_debug2:
                    # We dig into some internals for debug logs
                    base_comp = cast(MessageComputation, computation)
                    computation.logger.debug2(
                        "OPCODE: 0x%x (%s) | pc: %s | stack: %s",
                        opcode,
                        opcode_fn.mnemonic,
                        max(0, computation.code.program_counter - 1),
                        base_comp._stack,
                    )

                try:
                    opcode_fn(computation=computation)
                except Halt:
                    break

        return computation

    # -- context manager API -- #
    def __enter__(self) -> MessageComputationAPI:
        super().__enter__()
        if self.logger.show_debug2:
            self.logger.debug2(
                (
                    "MESSAGE COMPUTATION: "
                    "from: %s | to: %s | value: %s | depth %s | static: %s | gas: %s"
                ),
                encode_hex(self.msg.sender),
                encode_hex(self.msg.to),
                self.msg.value,
                self.msg.depth,
                "y" if self.msg.is_static else "n",
                self.msg.gas,
            )

        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        if exc_value and isinstance(exc_value, VMError):
            if self.logger.show_debug2:
                self.logger.debug2(
                    (
                        "MESSAGE COMPUTATION ERROR: "
                        "gas: %s | from: %s | to: %s | value: %s | "
                        "depth: %s | static: %s | error: %s"
                    ),
                    self.msg.gas,
                    encode_hex(self.msg.sender),
                    encode_hex(self.msg.to),
                    self.msg.value,
                    self.msg.depth,
                    "y" if self.msg.is_static else "n",
                    exc_value,
                )
            return super().__exit__(exc_type, exc_value, traceback)
        elif exc_type is None and self.logger.show_debug2:
            super().__exit__(exc_type, exc_value, traceback)
            self.logger.debug2(
                (
                    "MESSAGE COMPUTATION SUCCESS: "
                    "from: %s | to: %s | value: %s | depth: %s | static: %s "
                    "| gas-used: %s | gas-remaining: %s"
                ),
                encode_hex(self.msg.sender),
                encode_hex(self.msg.to),
                self.msg.value,
                self.msg.depth,
                "y" if self.msg.is_static else "n",
                self.get_gas_used(),
                self._gas_meter.gas_remaining,
            )

        return None
