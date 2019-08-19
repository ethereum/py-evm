from abc import abstractmethod
from typing import (
    Iterable,
    Tuple,
    Type,
)

from eth_typing import Hash32

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.fork_choice.scoring import ScoringFn as ForkChoiceScoringFn
from eth2.beacon.types.states import (
    BeaconState,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)

from trinity._utils.async_dispatch import async_method


class BaseAsyncBeaconChainDB(BeaconChainDB):
    """
    Abstract base class defines async counterparts of the sync ``BaseBeaconChainDB`` APIs.
    """

    @abstractmethod
    async def coro_persist_block(
            self,
            block: BaseBeaconBlock,
            block_class: Type[BaseBeaconBlock],
            fork_choice_scoring: ForkChoiceScoringFn,
    ) -> Tuple[Tuple[bytes, ...], Tuple[bytes, ...]]:
        ...

    #
    # Canonical Chain API
    #

    @abstractmethod
    async def coro_get_canonical_block_root(self, slot: int) -> Hash32:
        ...

    @abstractmethod
    async def coro_get_genesis_block_root(self) -> Hash32:
        ...

    @abstractmethod
    async def coro_get_canonical_block_by_slot(
            self,
            slot: int,
            block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        ...

    @abstractmethod
    async def coro_get_canonical_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        ...

    @abstractmethod
    async def coro_get_canonical_head_root(self)-> Hash32:
        ...

    @abstractmethod
    async def coro_get_finalized_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        ...

    @abstractmethod
    async def coro_get_block_by_root(self,
                                     block_root: Hash32,
                                     block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        ...

    @abstractmethod
    async def coro_get_score(self, block_root: Hash32) -> int:
        ...

    @abstractmethod
    async def coro_block_exists(self, block_root: Hash32) -> bool:
        ...

    @abstractmethod
    async def coro_persist_block_chain(
            self,
            blocks: Iterable[BaseBeaconBlock],
            block_class: Type[BaseBeaconBlock],
            fork_choice_scorings: Iterable[ForkChoiceScoringFn],
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        ...

    #
    # Beacon State
    #
    @abstractmethod
    async def coro_get_state_by_root(self, state_root: Hash32) -> BeaconState:
        ...

    @abstractmethod
    async def coro_persist_state(self,
                                 state: BeaconState) -> None:
        ...

    #
    # Attestation API
    #
    @abstractmethod
    async def coro_get_attestation_key_by_root(self, attestation_root: Hash32)-> Tuple[Hash32, int]:
        ...

    @abstractmethod
    async def coro_attestation_exists(self, attestation_root: Hash32) -> bool:
        ...

    #
    # Raw Database API
    #
    @abstractmethod
    async def coro_exists(self, key: bytes) -> bool:
        ...

    @abstractmethod
    async def coro_get(self, key: bytes) -> bytes:
        ...


class AsyncBeaconChainDB(BaseAsyncBeaconChainDB):
    coro_persist_block = async_method(BaseAsyncBeaconChainDB.persist_block)
    coro_get_canonical_block_root = async_method(BaseAsyncBeaconChainDB.get_canonical_block_root)  # noqa: E501
    coro_get_genesis_block_root = async_method(BaseAsyncBeaconChainDB.get_genesis_block_root)
    coro_get_canonical_block_by_slot = async_method(BaseAsyncBeaconChainDB.get_canonical_block_by_slot)  # noqa: E501
    coro_get_canonical_head = async_method(BaseAsyncBeaconChainDB.get_canonical_head)
    coro_get_canonical_head_root = async_method(BaseAsyncBeaconChainDB.get_canonical_head_root)  # noqa: E501
    coro_get_finalized_head = async_method(BaseAsyncBeaconChainDB.get_finalized_head)
    coro_get_block_by_root = async_method(BaseAsyncBeaconChainDB.get_block_by_root)
    coro_get_score = async_method(BaseAsyncBeaconChainDB.get_score)
    coro_block_exists = async_method(BaseAsyncBeaconChainDB.block_exists)
    coro_persist_block_chain = async_method(BaseAsyncBeaconChainDB.persist_block_chain)
    coro_get_state_by_root = async_method(BaseAsyncBeaconChainDB.get_state_by_root)
    coro_persist_state = async_method(BaseAsyncBeaconChainDB.persist_state)
    coro_get_attestation_key_by_root = async_method(BaseAsyncBeaconChainDB.get_attestation_key_by_root)  # noqa: E501
    coro_attestation_exists = async_method(BaseAsyncBeaconChainDB.attestation_exists)
    coro_exists = async_method(BaseAsyncBeaconChainDB.exists)
    coro_get = async_method(BaseAsyncBeaconChainDB.get)
