from evm.rlp.headers import BlockHeader

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evm.db.chain import BaseChainDB  # noqa: F401


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


def apply_state_dict(account_db, state_dict):
    for account, account_data in state_dict.items():
        account_db.set_balance(account, account_data["balance"])
        account_db.set_nonce(account, account_data["nonce"])
        account_db.set_code(account, account_data["code"])

        for slot, value in account_data["storage"].items():
            account_db.set_storage(account, slot, value)

    return account_db
