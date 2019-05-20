from abc import (
    ABC,
    abstractmethod,
)
# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseProxy,
)
from typing import (
    Iterable,
    Tuple,
    Type,
)

from eth_typing import Hash32

from eth2.beacon.types.states import (
    BeaconState,
)
from eth2.beacon.types.blocks import (  # noqa: F401
    BaseBeaconBlock,
)

from trinity._utils.mp import (
    async_method,
)
from eth2.configs import (
    Eth2Config,
)


class BaseAsyncBeaconChainDB(ABC):
    """
    Abstract base class defines async counterparts of the sync ``BaseBeaconChainDB`` APIs.
    """
    genesis_config: Eth2Config

    @abstractmethod
    async def coro_persist_block(
            self,
            block: BaseBeaconBlock,
            block_class: Type[BaseBeaconBlock]
    ) -> Tuple[Tuple[bytes, ...], Tuple[bytes, ...]]:
        pass

    #
    # Canonical Chain API
    #

    @abstractmethod
    async def coro_get_canonical_block_root(self, slot: int) -> Hash32:
        pass

    @abstractmethod
    async def coro_get_canonical_block_by_slot(
            self,
            slot: int,
            block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    async def coro_get_canonical_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    async def coro_get_canonical_head_root(self)-> Hash32:
        pass

    @abstractmethod
    async def coro_get_finalized_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    async def coro_get_block_by_root(self,
                                     block_root: Hash32,
                                     block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    async def coro_get_score(self, block_root: Hash32) -> int:
        pass

    @abstractmethod
    async def coro_block_exists(self, block_root: Hash32) -> bool:
        pass

    @abstractmethod
    async def coro_persist_block_chain(
            self,
            blocks: Iterable[BaseBeaconBlock],
            block_class: Type[BaseBeaconBlock]
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        pass

    #
    # Beacon State
    #
    @abstractmethod
    async def coro_get_state_by_root(self, state_root: Hash32) -> BeaconState:
        pass

    @abstractmethod
    async def coro_persist_state(self,
                                 state: BeaconState) -> None:
        pass

    #
    # Raw Database API
    #
    @abstractmethod
    async def coro_exists(self, key: bytes) -> bool:
        pass

    @abstractmethod
    async def coro_get(self, key: bytes) -> bytes:
        pass


class AsyncBeaconChainDBPreProxy(BaseAsyncBeaconChainDB):
    """
    Proxy implementation of ``BaseAsyncBeaconChainDB`` that does not derive from
    ``BaseProxy`` for the purpose of improved testability.
    """

    coro_persist_block = async_method('persist_block')
    coro_get_canonical_block_root = async_method('get_canonical_block_root')
    coro_get_canonical_block_by_slot = async_method('get_canonical_block_by_slot')
    coro_get_canonical_head = async_method('get_canonical_head')
    coro_get_canonical_head_root = async_method('get_canonical_head_root')
    coro_get_finalized_head = async_method('get_finalized_head')
    coro_get_block_by_root = async_method('get_block_by_root')
    coro_get_score = async_method('get_score')
    coro_block_exists = async_method('block_exists')
    coro_persist_block_chain = async_method('persist_block_chain')
    coro_get_state_by_root = async_method('get_state_by_root')
    coro_persist_state = async_method('persist_state')
    coro_exists = async_method('exists')
    coro_get = async_method('get')


class AsyncBeaconChainDBProxy(BaseProxy, AsyncBeaconChainDBPreProxy):
    """
    Turn ``AsyncBeaconChainDBPreProxy`` into an actual proxy by deriving from ``BaseProxy``
    """
    pass
