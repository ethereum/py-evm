from typing import (
    Dict,
    Tuple,
    TypeVar,
)

from eth.rlp.receipts import Receipt
from eth_typing import (
    Hash32,
)
from p2p.peer import BasePeer

from trinity.rlp.block_body import BlockBody

TPeer = TypeVar('TPeer', bound=BasePeer)

# A payload ready to send with a peer command
TCommandPayload = TypeVar('TCommandPayload')

# A payload delivered by a responding command
TMsg = TypeVar('TMsg')

# The returned value at the end of an exchange
TResult = TypeVar('TResult')

NodeDataBundles = Tuple[Tuple[Hash32, bytes], ...]

ReceiptsBundles = Tuple[Tuple[Tuple[Receipt, ...], Tuple[Hash32, Dict[Hash32, bytes]]], ...]
ReceiptsByBlock = Tuple[Tuple[Receipt, ...], ...]

# (BlockBody, (txn_root, txn_trie_data), uncles_hash)
BlockBodyBundles = Tuple[Tuple[
    BlockBody,
    Tuple[Hash32, Dict[Hash32, bytes]],
    Hash32,
], ...]
