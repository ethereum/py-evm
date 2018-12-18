from trinity._utils.async_dispatch import (
    async_method,
)

from .base import BaseAsyncChain


class AsyncChainMixin(BaseAsyncChain):
    coro_get_block_by_hash = async_method('get_block_by_hash')
    coro_get_block_by_header = async_method('get_block_by_header')
    coro_get_canonical_block_by_number = async_method('get_canonical_block_by_number')
    coro_import_block = async_method('import_block')
    coro_validate_chain = async_method('validate_chain')
    coro_validate_receipt = async_method('validate_receipt')
