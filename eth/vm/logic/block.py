from eth.vm.computation import (
    MessageComputation,
)


def blockhash(computation: MessageComputation) -> None:
    block_number = computation.stack_pop1_int()

    block_hash = computation.state.get_ancestor_hash(block_number)

    computation.stack_push_bytes(block_hash)


def coinbase(computation: MessageComputation) -> None:
    computation.stack_push_bytes(computation.state.coinbase)


def timestamp(computation: MessageComputation) -> None:
    computation.stack_push_int(computation.state.timestamp)


def number(computation: MessageComputation) -> None:
    computation.stack_push_int(computation.state.block_number)


def difficulty(computation: MessageComputation) -> None:
    computation.stack_push_int(computation.state.difficulty)


def gaslimit(computation: MessageComputation) -> None:
    computation.stack_push_int(computation.state.gas_limit)


def basefee(computation: MessageComputation) -> None:
    computation.stack_push_int(computation.state.base_fee)


def mixhash(computation: MessageComputation) -> None:
    computation.stack_push_bytes(computation.state.mix_hash)
