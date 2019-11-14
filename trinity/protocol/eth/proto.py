from typing import (
    TYPE_CHECKING,
)

from eth_utils import (
    get_extended_debug_logger,
)

from p2p.protocol import BaseProtocol

from .commands import (
    BlockBodies,
    BlockHeaders,
    GetBlockBodies,
    GetBlockHeaders,
    GetNodeData,
    GetReceipts,
    NewBlock,
    NewBlockHashes,
    NodeData,
    Receipts,
    Status,
    Transactions,
)

if TYPE_CHECKING:
    from .peer import ETHPeer  # noqa: F401


class ETHProtocol(BaseProtocol):
    name = 'eth'
    version = 63
    commands = (
        Status,
        NewBlockHashes,
        Transactions,
        GetBlockHeaders, BlockHeaders,
        GetBlockBodies, BlockBodies,
        NewBlock,
        GetNodeData, NodeData,
        GetReceipts, Receipts,
    )
    command_length = 17

    logger = get_extended_debug_logger('trinity.protocol.eth.proto.ETHProtocol')
