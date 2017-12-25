from evm import constants


def blockhash(computation):
    block_number = computation.stack.pop(type_hint=constants.UINT256)

    block_hash = computation.state.get_ancestor_hash(block_number)

    computation.stack.push(block_hash)


def coinbase(computation):
    computation.stack.push(computation.state.coinbase)


def timestamp(computation):
    computation.stack.push(computation.state.timestamp)


def number(computation):
    computation.stack.push(computation.state.block_number)


def difficulty(computation):
    computation.stack.push(computation.state.difficulty)


def gaslimit(computation):
    computation.stack.push(computation.state.gas_limit)
