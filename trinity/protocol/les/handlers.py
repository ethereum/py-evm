from trinity.protocol.common.handlers import (
    BaseChainExchangeHandler,
)

from .exchanges import GetBlockHeadersExchange


class LESExchangeHandler(BaseChainExchangeHandler):
    _exchange_config = {
        'get_block_headers': GetBlockHeadersExchange,
    }
