from trinity.protocol.common.handlers import (
    BaseExchangeHandler,
)

from .exchanges import GetBlockHeadersExchange


class LESExchangeHandler(BaseExchangeHandler):
    _exchanges = {
        'get_block_headers': GetBlockHeadersExchange,
    }

    get_block_headers: GetBlockHeadersExchange
