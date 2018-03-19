from evm import constants


def blockhash(computation):
    block_number = computation.stack_pop(type_hint=constants.UINT256)

    block_hash = computation.vm_state.get_ancestor_hash(block_number)

    computation.stack_push(block_hash)


def coinbase(computation):
    computation.stack_push(computation.vm_state.coinbase)


def timestamp(computation):
    computation.stack_push(computation.vm_state.timestamp)


def number(computation):
    computation.stack_push(computation.vm_state.block_number)


def difficulty(computation):
    computation.stack_push(computation.vm_state.difficulty)


def gaslimit(computation):
    computation.stack_push(computation.vm_state.gas_limit)
