from trinity.protocol.common.handlers import (
    BaseChainExchangeHandler,
)

from .exchanges import GetBlockHeadersExchange, GetNodeDataExchange


class LESExchangeHandler(BaseChainExchangeHandler):
    _exchange_config = {
        'get_block_headers': GetBlockHeadersExchange,
        'get_node_data': GetNodeDataExchange,
    }

    # These are needed only to please mypy.
    get_node_data: GetNodeDataExchange
