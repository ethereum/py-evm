from typing import (
    TYPE_CHECKING,
)

from eth_typing import (
    Hash32,
)

from eth.rlp.headers import (
    BlockHeader,
)
from eth.typing import (
    AccountState,
)
from eth.vm.state import (
    BaseState,
)

if TYPE_CHECKING:
    from eth.db.chain import BaseChainDB  # noqa: F401


def get_parent_header(block_header: BlockHeader, db: 'BaseChainDB') -> BlockHeader:
    """
    Returns the header for the parent block.
    """
    return db.get_block_header_by_hash(block_header.parent_hash)


def get_block_header_by_hash(block_hash: Hash32, db: 'BaseChainDB') -> BlockHeader:
    """
    Returns the header for the parent block.
    """
    return db.get_block_header_by_hash(block_hash)


def apply_state_dict(state: BaseState, state_dict: AccountState) -> None:
    for account, account_data in state_dict.items():
        state.set_balance(account, account_data["balance"])
        state.set_nonce(account, account_data["nonce"])
        state.set_code(account, account_data["code"])

        for slot, value in account_data["storage"].items():
            state.set_storage(account, slot, value)
