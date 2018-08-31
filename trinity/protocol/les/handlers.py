from trinity.protocol.common.handlers import (
    BaseExchangeHandler,
)

from .exchanges import GetBlockHeadersExchange


class LESExchangeHandler(BaseExchangeHandler):
    _exchange_config = {
        'get_block_headers': GetBlockHeadersExchange,
    }

    get_block_headers: GetBlockHeadersExchange
