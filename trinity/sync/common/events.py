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


class SyncingResponse(BaseEvent):
    def __init__(self, is_syncing: bool, progress: Optional[SyncProgress]) -> None:
        super().__init__()
        self.is_syncing: bool = is_syncing
        self.progress: Optional[SyncProgress] = progress


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


class CollectMissingAccount(BaseRequestResponseEvent[MissingAccountCollected]):
    """
    Beam Sync has been paused because the given address and/or missing_node_hash
    is missing from the state DB, at the given state root hash.
    """
    def __init__(
            self,
            missing_node_hash: Hash32,
            address_hash: Hash32,
            state_root_hash: Hash32) -> None:
        super().__init__()
        self.missing_node_hash = missing_node_hash
        self.address_hash = address_hash
        self.state_root_hash = state_root_hash

    @staticmethod
    def expected_response_type() -> Type[MissingAccountCollected]:
        return MissingAccountCollected


class MissingBytecodeCollected(BaseEvent):
    """
    Response to :cls:`CollectMissingBytecode`, emitted only after the bytecode has
    been downloaded from a peer, and can be retrieved in the database.
    """
    pass


class CollectMissingBytecode(BaseRequestResponseEvent[MissingBytecodeCollected]):
    """
    Beam Sync has been paused because the given bytecode
    is missing from the state DB, at the given state root hash.
    """
    def __init__(self, bytecode_hash: Hash32) -> None:
        super().__init__()
        self.bytecode_hash = bytecode_hash

    @staticmethod
    def expected_response_type() -> Type[MissingBytecodeCollected]:
        return MissingBytecodeCollected


class MissingStorageCollected(BaseEvent):
    """
    Response to :cls:`CollectMissingStorage`, emitted only after the storage value has
    been downloaded from a peer, and can be retrieved in the database.
    """
    pass


class CollectMissingStorage(BaseRequestResponseEvent[MissingStorageCollected]):
    """
    Beam Sync has been paused because the given storage key and/or missing_node_hash
    is missing from the state DB, at the given state root hash.
    """
    def __init__(
            self,
            missing_node_hash: Hash32,
            storage_key: Hash32,
            storage_root_hash: Hash32,
            account_address: Address) -> None:

        super().__init__()
        self.missing_node_hash = missing_node_hash
        self.storage_key = storage_key
        self.storage_root_hash = storage_root_hash
        self.account_address = account_address

    @staticmethod
    def expected_response_type() -> Type[MissingStorageCollected]:
        return MissingStorageCollected


class StatelessBlockImportDone(BaseEvent):
    """
    Response to :cls:`DoStatelessBlockImport`, emitted only after the block has
    been fully imported. This event is emitted whether the import was successful
    or a failure.
    """
    def __init__(
            self,
            block: BaseBlock,
            completed: bool,
            result: Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]],
            exception: BaseException) -> None:
        super().__init__()
        self.block = block
        self.completed = completed
        self.result = result
        self.exception = exception


class DoStatelessBlockImport(BaseRequestResponseEvent[StatelessBlockImportDone]):
    """
    The syncer emits this event when it would like the Beam Sync process to
    start attempting a block import.
    """
    def __init__(self, block: BaseBlock) -> None:
        super().__init__()
        self.block = block

    @staticmethod
    def expected_response_type() -> Type[StatelessBlockImportDone]:
        return StatelessBlockImportDone
