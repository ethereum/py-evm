from evm import constants


def blockhash(computation):
    block_number = computation.stack.pop(type_hint=constants.UINT256)

    block_hash = computation.evm.get_block_hash(block_number)

    computation.stack.push(block_hash)


def coinbase(computation):
    computation.stack.push(computation.evm.block.header.coinbase)


def timestamp(computation):
    computation.stack.push(computation.evm.block.header.timestamp)


def number(computation):
    computation.stack.push(computation.evm.block.header.block_number)


def difficulty(computation):
    computation.stack.push(computation.evm.block.header.difficulty)


def gaslimit(computation):
    computation.stack.push(computation.evm.block.header.gas_limit)
