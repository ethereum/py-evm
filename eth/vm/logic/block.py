from eth_typing import (
    BlockNumber,
)

from eth.abc import (
    ComputationAPI,
)


def blockhash(computation: ComputationAPI) -> None:
    block_number = computation.stack_pop1_int()

    block_hash = computation.state.get_ancestor_hash(BlockNumber(block_number))

    computation.stack_push_bytes(block_hash)


def coinbase(computation: ComputationAPI) -> None:
    computation.stack_push_bytes(computation.state.coinbase)


def timestamp(computation: ComputationAPI) -> None:
    computation.stack_push_int(computation.state.timestamp)


def number(computation: ComputationAPI) -> None:
    computation.stack_push_int(computation.state.block_number)


def difficulty(computation: ComputationAPI) -> None:
    computation.stack_push_int(computation.state.difficulty)


def gaslimit(computation: ComputationAPI) -> None:
    computation.stack_push_int(computation.state.gas_limit)


def basefee(computation: ComputationAPI) -> None:
    computation.stack_push_int(computation.state.base_fee)


def mixhash(computation: ComputationAPI) -> None:
    computation.stack_push_bytes(computation.state.mix_hash)
