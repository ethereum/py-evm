import logging

from evm import constants


logger = logging.getLogger('evm.logic.block')


def blockhash(computation):
    block_number = computation.stack.pop(type_hint=constants.UINT256)

    block_hash = computation.evm.get_block_hash(block_number)

    logger.info('BLOCKHASH: %s', block_hash)

    computation.stack.push(block_hash)


def coinbase(computation):
    logger.info('COINBASE: %s', computation.env.coinbase)
    computation.stack.push(computation.env.coinbase)


def timestamp(computation):
    logger.info('TIMESTAMP: %s', computation.env.timestamp)
    computation.stack.push(computation.env.timestamp)


def number(computation):
    logger.info('NUMBER: %s', computation.env.block_number)
    computation.stack.push(computation.env.block_number)


def difficulty(computation):
    logger.info('DIFFICULTY: %s', computation.env.difficulty)
    computation.stack.push(computation.env.difficulty)


def gaslimit(computation):
    logger.info('GASLIMIT: %s', computation.env.gas_limit)
    computation.stack.push(computation.env.gas_limit)
