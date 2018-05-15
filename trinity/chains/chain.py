from abc import abstractmethod
# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseProxy,
)
from typing import (
    Dict,
    Type,
)

from evm.chains.base import (
    AccountState,
    BaseChain,
    Chain,
)
from evm.db.backends.base import BaseDB
from evm.db.chain import (
    BaseChainDB,
)
from evm.db.header import (
    BaseHeaderDB,
)
from evm.rlp.headers import (
    BlockHeader,
    HeaderParams,
)
from evm.rlp.blocks import BaseBlock

from trinity.utils.mp import (
    async_method,
    sync_method,
)


class BaseAsyncChain(BaseChain):
    @abstractmethod
    async def coro_import_block(self, block: BaseBlock) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")


class AsyncChain(Chain, BaseAsyncChain):
    async def coro_import_block(self, block: BaseBlock) -> BaseBlock:
        raise NotImplementedError("Chain classes must implement this method")


class AsyncChainProxy(BaseProxy, BaseAsyncChain):
    #
    # Async Proxy Methods
    #
    coro_import_block = async_method('import_block')

    #
    # APIS not available on the proxy class
    #
    def get_chaindb_class(cls) -> Type[BaseChainDB]:
        raise NotImplementedError("Chain classes must implement this method")

    @classmethod
    def get_headerdb_class(cls) -> Type[BaseHeaderDB]:
        raise NotImplementedError("Chain classes must implement this method")

    @classmethod
    def from_genesis(cls,
                     base_db: BaseDB,
                     genesis_params: Dict[str, HeaderParams],
                     genesis_state: AccountState=None) -> 'BaseChain':
        raise NotImplementedError("Chain classes must implement this method")

    @classmethod
    def from_genesis_header(cls,
                            base_db: BaseDB,
                            genesis_header: BlockHeader) -> 'BaseChain':
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    def get_chain_at_block_parent(self, block: BaseBlock) -> 'BaseChain':
        raise NotImplementedError("Chain classes must implement this method")

    #
    # Sync Proxy Methods
    #
    get_vm = sync_method('get_vm')
    get_vm_class_for_block_number = sync_method('get_vm_class_for_block_number')
    create_header_from_parent = sync_method('create_header_from_parent')
    get_block_header_by_hash = sync_method('get_block_header_by_hash')
    get_canonical_head = sync_method('get_canonical_head')
    get_ancestors = sync_method('get_ancestors')
    get_block = sync_method('get_block')
    get_block_by_hash = sync_method('get_block_by_hash')
    get_block_by_header = sync_method('get_block_by_header')
    get_canonical_block_by_number = sync_method('get_canonical_block_by_number')
    get_canonical_block_hash = sync_method('get_canonical_block_hash')
    create_transaction = sync_method('create_transaction')
    create_unsigned_transaction = sync_method('create_unsigned_transaction')
    get_canonical_transaction = sync_method('get_canonical_transaction')
    apply_transaction = sync_method('apply_transaction')
    estimate_gas = sync_method('estimate_gas')
    import_block = sync_method('import_block')
    mine_block = sync_method('mine_block')
    validate_block = sync_method('validate_block')
    validate_gaslimit = sync_method('validate_gaslimit')
    validate_seal = sync_method('validate_seal')
    validate_uncles = sync_method('validate_uncles')
