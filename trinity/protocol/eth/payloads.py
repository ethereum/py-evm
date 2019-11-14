from typing import NamedTuple, Tuple

from eth_typing import BlockNumber, Hash32

from eth.abc import BlockHeaderAPI, TransactionFieldsAPI


class StatusPayload(NamedTuple):
    version: int
    network_id: int
    total_difficulty: int
    head_hash: Hash32
    genesis_hash: Hash32


class NewBlockHash(NamedTuple):
    hash: Hash32
    number: BlockNumber


class BlockFields(NamedTuple):
    header: BlockHeaderAPI
    transactions: Tuple[TransactionFieldsAPI, ...]
    uncles: Tuple[BlockHeaderAPI, ...]


class NewBlockPayload(NamedTuple):
    block: BlockFields
    total_difficulty: int
