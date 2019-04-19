from typing import Type  # noqa: F401

from eth_bloom import (
    BloomFilter,
)

from eth.constants import (
    BLOCK_REWARD,
    UNCLE_DEPTH_PENALTY_FACTOR,
    ZERO_HASH32,
)

from eth.rlp.blocks import BaseBlock  # noqa: F401
from eth.rlp.headers import BlockHeader
from eth.rlp.logs import Log
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransaction

from eth.vm.base import VM
from eth.vm.computation import BaseComputation
from eth.vm.state import BaseState  # noqa: F401

from .blocks import FrontierBlock
from .state import FrontierState
from .headers import (
    create_frontier_header_from_parent,
    compute_frontier_difficulty,
    configure_frontier_header,
)
from .validation import validate_frontier_transaction_against_header


def make_frontier_receipt(base_header: BlockHeader,
                          transaction: BaseTransaction,
                          computation: BaseComputation) -> Receipt:
    # Reusable for other forks
    # This skips setting the state root (set to 0 instead). The logic for making a state root
    # lives in the FrontierVM, so that state merkelization at each receipt is skipped at Byzantium+.

    logs = [
        Log(address, topics, data)
        for address, topics, data
        in computation.get_log_entries()
    ]

    gas_remaining = computation.get_gas_remaining()
    gas_refund = computation.get_gas_refund()
    tx_gas_used = (
        transaction.gas - gas_remaining
    ) - min(
        gas_refund,
        (transaction.gas - gas_remaining) // 2,
    )
    gas_used = base_header.gas_used + tx_gas_used

    receipt = Receipt(
        state_root=ZERO_HASH32,
        gas_used=gas_used,
        logs=logs,
    )

    return receipt


class FrontierVM(VM):
    # fork name
    fork = 'frontier'  # type: str

    # classes
    block_class = FrontierBlock  # type: Type[BaseBlock]
    _state_class = FrontierState  # type: Type[BaseState]

    # methods
    create_header_from_parent = staticmethod(create_frontier_header_from_parent)    # type: ignore
    compute_difficulty = staticmethod(compute_frontier_difficulty)      # type: ignore
    configure_header = configure_frontier_header
    validate_transaction_against_header = validate_frontier_transaction_against_header

    @staticmethod
    def get_block_reward() -> int:
        return BLOCK_REWARD

    @staticmethod
    def get_uncle_reward(block_number: int, uncle: BaseBlock) -> int:
        return BLOCK_REWARD * (
            UNCLE_DEPTH_PENALTY_FACTOR + uncle.block_number - block_number
        ) // UNCLE_DEPTH_PENALTY_FACTOR

    @classmethod
    def get_nephew_reward(cls) -> int:
        return cls.get_block_reward() // 32

    def add_receipt_to_header(self, old_header: BlockHeader, receipt: Receipt) -> BlockHeader:
        return old_header.copy(
            bloom=int(BloomFilter(old_header.bloom) | receipt.bloom),
            gas_used=receipt.gas_used,
            state_root=self.state.make_state_root(),
        )

    @staticmethod
    def make_receipt(
            base_header: BlockHeader,
            transaction: BaseTransaction,
            computation: BaseComputation,
            state: BaseState) -> Receipt:

        receipt_without_state_root = make_frontier_receipt(base_header, transaction, computation)

        return receipt_without_state_root.copy(
            state_root=state.make_state_root()
        )
