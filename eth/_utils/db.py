from eth_typing import (
    Hash32,
)

from eth.abc import (
    BlockHeaderAPI,
    ChainDatabaseAPI,
    StateAPI,
)
from eth.typing import (
    AccountState,
)


def get_parent_header(block_header: BlockHeaderAPI, db: ChainDatabaseAPI) -> BlockHeaderAPI:
    """
    Returns the header for the parent block.
    """
    return db.get_block_header_by_hash(block_header.parent_hash)


def get_block_header_by_hash(block_hash: Hash32, db: ChainDatabaseAPI) -> BlockHeaderAPI:
    """
    Returns the header for the parent block.
    """
    return db.get_block_header_by_hash(block_hash)


def apply_state_dict(state: StateAPI, state_dict: AccountState) -> None:
    for account, account_data in state_dict.items():
        balance, nonce, code, storage = (
            account_data["balance"],
            account_data["nonce"],
            account_data["code"],
            account_data["storage"],
        )
        state.set_balance(account, balance)
        state.set_nonce(account, nonce)
        state.set_code(account, code)

        for slot, value in storage.items():
            state.set_storage(account, slot, value)
