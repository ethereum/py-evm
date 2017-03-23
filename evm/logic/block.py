import logging

from evm.utils.numeric import (
    int_to_big_endian,
    big_endian_to_int,
)


logger = logging.getLogger('evm.logic.block')


def blockhash(computation):
    block_number = big_endian_to_int(computation.stack.pop())
    block_hash = computation.evm.get_block_hash(block_number)
    logger.info('BLOCKHASH: %s', block_hash)
    computation.stack.push(block_hash)


def coinbase(computation):
    logger.info('COINBASE: %s', computation.env.coinbase)
    computation.stack.push(computation.env.coinbase)


def timestamp(computation):
    logger.info('TIMESTAMP: %s', computation.env.timestamp)
    computation.stack.push(int_to_big_endian(computation.env.timestamp))


def number(computation):
    logger.info('NUMBER: %s', computation.env.block_number)
    computation.stack.push(int_to_big_endian(computation.env.block_number))


def difficulty(computation):
    logger.info('DIFFICULTY: %s', computation.env.difficulty)
    computation.stack.push(int_to_big_endian(computation.env.difficulty))


def gaslimit(computation):
    logger.info('GASLIMIT: %s', computation.env.gas_limit)
    computation.stack.push(int_to_big_endian(computation.env.gas_limit))
