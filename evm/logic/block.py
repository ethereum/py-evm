from evm import constants


def blockhash(computation):
    block_number = computation.stack.pop(type_hint=constants.UINT256)

    block_hash = computation.evm.get_block_hash(block_number)

    computation.stack.push(block_hash)


def coinbase(computation):
    computation.stack.push(computation.env.coinbase)


def timestamp(computation):
    computation.stack.push(computation.env.timestamp)


def number(computation):
    computation.stack.push(computation.env.block_number)


def difficulty(computation):
    computation.stack.push(computation.env.difficulty)


def gaslimit(computation):
    computation.stack.push(computation.env.gas_limit)
