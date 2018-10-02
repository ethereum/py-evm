# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import BaseProxy  # type: ignore

from trinity.utils.mp import (
    async_method,
    sync_method,
)


class ChainProxy(BaseProxy):
    coro_import_block = async_method('import_block')
    coro_validate_chain = async_method('validate_chain')
    coro_validate_receipt = async_method('validate_receipt')
    get_vm_configuration = sync_method('get_vm_configuration')
    get_vm_class = sync_method('get_vm_class')
    get_vm_class_for_block_number = sync_method('get_vm_class_for_block_number')
