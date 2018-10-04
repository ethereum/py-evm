from trinity.protocol.common.handlers import (
    BaseChainExchangeHandler,
)

from .exchanges import (
    GetBlockBodiesExchange,
    GetBlockHeadersExchange,
    GetNodeDataExchange,
    GetReceiptsExchange,
)


class ETHExchangeHandler(BaseChainExchangeHandler):
    _exchange_config = {
        'get_block_bodies': GetBlockBodiesExchange,
        'get_block_headers': GetBlockHeadersExchange,
        'get_node_data': GetNodeDataExchange,
        'get_receipts': GetReceiptsExchange,
    }

    # These are needed only to please mypy.
    get_block_bodies: GetBlockBodiesExchange
    get_node_data: GetNodeDataExchange
    get_receipts: GetReceiptsExchange
