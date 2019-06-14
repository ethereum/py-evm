from dataclasses import (
    dataclass,
)
from typing import (
    Optional,
    Tuple,
    Type,
)

from eth.rlp.blocks import BaseBlock
from eth_typing import (
    Address,
    Hash32,
)
from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

from trinity.sync.common.types import (
    SyncProgress
)


@dataclass
class SyncingResponse(BaseEvent):
    is_syncing: bool
    progress: Optional[SyncProgress]


class SyncingRequest(BaseRequestResponseEvent[SyncingResponse]):
    @staticmethod
    def expected_response_type() -> Type[SyncingResponse]:
        return SyncingResponse


class MissingAccountCollected(BaseEvent):
    """
    Response to :cls:`CollectMissingAccount`, emitted only after the account has
    been downloaded from a peer, and can be retrieved in the database.
    """
    pass


@dataclass
class CollectMissingAccount(BaseRequestResponseEvent[MissingAccountCollected]):
    """
    Beam Sync has been paused because the given address and/or missing_node_hash
    is missing from the state DB, at the given state root hash.
    """
    missing_node_hash: Hash32
    address_hash: Hash32
    state_root_hash: Hash32

    @staticmethod
    def expected_response_type() -> Type[MissingAccountCollected]:
        return MissingAccountCollected


class MissingBytecodeCollected(BaseEvent):
    """
    Response to :cls:`CollectMissingBytecode`, emitted only after the bytecode has
    been downloaded from a peer, and can be retrieved in the database.
    """
    pass


@dataclass
class CollectMissingBytecode(BaseRequestResponseEvent[MissingBytecodeCollected]):
    """
    Beam Sync has been paused because the given bytecode
    is missing from the state DB, at the given state root hash.
    """
    bytecode_hash: Hash32

    @staticmethod
    def expected_response_type() -> Type[MissingBytecodeCollected]:
        return MissingBytecodeCollected


class MissingStorageCollected(BaseEvent):
    """
    Response to :cls:`CollectMissingStorage`, emitted only after the storage value has
    been downloaded from a peer, and can be retrieved in the database.
    """
    pass


@dataclass
class CollectMissingStorage(BaseRequestResponseEvent[MissingStorageCollected]):
    """
    Beam Sync has been paused because the given storage key and/or missing_node_hash
    is missing from the state DB, at the given state root hash.
    """

    missing_node_hash: Hash32
    storage_key: Hash32
    storage_root_hash: Hash32
    account_address: Address

    @staticmethod
    def expected_response_type() -> Type[MissingStorageCollected]:
        return MissingStorageCollected


@dataclass
class StatelessBlockImportDone(BaseEvent):
    """
    Response to :cls:`DoStatelessBlockImport`, emitted only after the block has
    been fully imported. This event is emitted whether the import was successful
    or a failure.
    """

    block: BaseBlock
    completed: bool
    result: Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]]
    # flake8 gets confused by the Tuple syntax above
    exception: BaseException  # noqa: E701


@dataclass
class DoStatelessBlockImport(BaseRequestResponseEvent[StatelessBlockImportDone]):
    """
    The syncer emits this event when it would like the Beam Sync process to
    start attempting a block import.
    """
    block: BaseBlock

    @staticmethod
    def expected_response_type() -> Type[StatelessBlockImportDone]:
        return StatelessBlockImportDone
