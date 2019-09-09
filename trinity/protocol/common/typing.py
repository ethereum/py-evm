from typing import (
    Any,
    Dict,
    Tuple,
    TypeVar,
)

from eth.abc import BlockAPI, ReceiptAPI
from eth_typing import (
    Hash32,
)

from p2p.abc import RequestAPI
from p2p.peer import BasePeer


TRequest = TypeVar('TRequest', bound=RequestAPI[Any])
TResponse = TypeVar('TResponse')
TResult = TypeVar('TResult')


TPeer = TypeVar('TPeer', bound=BasePeer)

# (
#   (node_hash, node),
#   ...
# )
NodeDataBundles = Tuple[Tuple[Hash32, bytes], ...]

# (receipts_in_block_a, receipts_in_block_b, ...)
ReceiptsByBlock = Tuple[Tuple[ReceiptAPI, ...], ...]

# (
#   (receipts_in_block_a, (receipts_root_hash, receipts_trie_nodes),
#   (receipts_in_block_b, (receipts_root_hash, receipts_trie_nodes),
#   ...
# (
ReceiptsBundles = Tuple[Tuple[Tuple[ReceiptAPI, ...], Tuple[Hash32, Dict[Hash32, bytes]]], ...]

# (BlockBody, (txn_root, txn_trie_data), uncles_hash)

BlockBodyBundle = Tuple[
    BlockAPI,
    Tuple[Hash32, Dict[Hash32, bytes]],
    Hash32,
]

BlockBodyBundles = Tuple[BlockBodyBundle, ...]
