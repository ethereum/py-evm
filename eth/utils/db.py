from typing import (
    Dict,
    Type,
    TYPE_CHECKING,
    Union,
)

from eth.db.account import (
    BaseAccountDB,
)

from eth.rlp.headers import (
    BlockHeader,
)

from eth_typing import (
    Address,
)

if TYPE_CHECKING:
    from eth.db.chain import BaseChainDB  # noqa: F401

# Mapping from address to account state.
# 'balance', 'nonce' -> int
# 'code' -> bytes
# 'storage' -> Dict[int, int]
AccountState = Dict[Address, Dict[str, Union[int, bytes, Dict[int, int]]]]

def get_parent_header(block_header: BlockHeader, db: 'BaseChainDB') -> BlockHeader:
    """
    Returns the header for the parent block.
    """
    return db.get_block_header_by_hash(block_header.parent_hash)


def get_block_header_by_hash(block_hash: BlockHeader, db: 'BaseChainDB') -> BlockHeader:
    """
    Returns the header for the parent block.
    """
    return db.get_block_header_by_hash(block_hash)


def apply_state_dict(account_db: BaseAccountDB, state_dict: AccountState) -> BaseAccountDB:

    for account, account_data in state_dict.items():
        assert isinstance(account_data["balance"], int)
        account_db.set_balance(account, account_data["balance"])

        assert isinstance(account_data["nonce"], int)
        account_db.set_nonce(account, account_data["nonce"])

        assert isinstance(account_data["code"], bytes)
        account_db.set_code(account, account_data["code"])

        assert isinstance(account_data["storage"], dict)
        for slot, value in account_data["storage"].items():
            account_db.set_storage(account, slot, value)

    return account_db
