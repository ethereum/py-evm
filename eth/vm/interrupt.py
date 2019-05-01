from typing import (
    NamedTuple,
    Tuple,
    TYPE_CHECKING,
)

from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    encode_hex,
)
from trie.exceptions import (
    MissingTrieNode,
)

from eth.exceptions import (
    PyEVMError,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.rlp.receipts import Receipt

if TYPE_CHECKING:
    from eth.vm.state import BaseState


class MidBlockState(NamedTuple):
    """
    The data needed to resume transaction execution from the middle of a block
    """
    state: 'BaseState'
    partial_header: BlockHeader
    completed_receipts: Tuple[Receipt, ...]
    applied_block_rewards: bool = False

    # how many transactions have already been completed
    @property
    def num_completed_transactions(self) -> int:
        return len(self.completed_receipts)


class EVMMissingData(PyEVMError):
    mid_block_state = None

    def set_mid_block_state(self, mid_block_state: MidBlockState):
        if self.mid_block_state is not None:
            raise ValidationError("Cannot set mid-block state twice")
        else:
            self.mid_block_state = mid_block_state

    def __str__(self):
        return "EVMMissingData at transaction index %r" % (
            self.mid_block_state.num_completed_transactions if self.mid_block_state else None,
        )


class MissingAccountTrieNode(EVMMissingData, MissingTrieNode):
    """
    Raised when a main state trie node is missing from the DB, to get an account RLP
    """

    @property
    def state_root_hash(self) -> Hash32:
        return self.root_hash

    @property
    def address_hash(self) -> Hash32:
        return self.requested_key

    def __repr__(self) -> str:
        return "MissingAccountTrieNode: {}".format(self)

    def __str__(self) -> str:
        superclass_str = EVMMissingData.__str__(self)
        return (
            "State trie database is missing node for hash {}, which is needed to look up account "
            "with address hash {} at root hash {} -- {}".format(
                encode_hex(self.missing_node_hash),
                encode_hex(self.address_hash),
                encode_hex(self.state_root_hash),
                superclass_str,
            )
        )


class MissingStorageTrieNode(EVMMissingData, MissingTrieNode):
    """
    Raised when a storage trie node is missing from the DB
    """
    def __init__(
            self,
            missing_node_hash: Hash32,
            storage_root_hash: Hash32,
            requested_key: Hash32,
            account_address: Address,
            *args: bytes) -> None:
        if not isinstance(account_address, bytes):
            raise TypeError("Account address must be bytes, was: %r" % account_address)

        super().__init__(
            missing_node_hash,
            storage_root_hash,
            requested_key,
            account_address,
            *args,
        )

    @property
    def storage_root_hash(self) -> Hash32:
        return self.root_hash

    @property
    def account_address(self) -> Address:
        return self.args[3]

    def __repr__(self) -> str:
        return "MissingStorageTrieNode: {}".format(self)

    def __str__(self) -> str:
        superclass_str = EVMMissingData.__str__(self)
        return (
            "Storage trie database is missing hash {} needed to look up key {} "
            "at root hash {} in account address {} -- {}".format(
                encode_hex(self.missing_node_hash),
                encode_hex(self.requested_key),
                encode_hex(self.root_hash),
                encode_hex(self.account_address),
                superclass_str,
            )
        )


class MissingBytecode(EVMMissingData):
    """
    Raised when the bytecode is missing from the database for a known bytecode hash.
    """
    def __init__(self, missing_code_hash: Hash32) -> None:
        if not isinstance(missing_code_hash, bytes):
            raise TypeError("Missing code hash must be bytes, was: %r" % missing_code_hash)

        super().__init__(missing_code_hash)

    @property
    def missing_code_hash(self) -> Hash32:
        return self.args[0]

    def __repr__(self) -> str:
        return "MissingBytecode: {}".format(self)

    def __str__(self) -> str:
        superclass_str = EVMMissingData.__str__(self)
        return "Database is missing bytecode for code hash {} -- {}".format(
            encode_hex(self.missing_code_hash),
            superclass_str,
        )
