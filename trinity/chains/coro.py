from trinity.utils.async_dispatch import (
    async_method,
)


class AsyncChainMixin:

    coro_get_canonical_block_by_number = async_method('get_canonical_block_by_number')
    coro_get_block_by_hash = async_method('get_block_by_hash')
    coro_get_block_by_header = async_method('get_block_by_header')
