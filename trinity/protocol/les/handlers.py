from trinity.protocol.common.handlers import (
    BaseChainExchangeHandler,
)

from .exchanges import GetBlockHeadersExchange, GetReceiptsExchange


class LESExchangeHandler(BaseChainExchangeHandler):
    _exchange_config = {
        'get_block_headers': GetBlockHeadersExchange,
        'get_receipts': GetReceiptsExchange,
    }

    # These are needed only to please mypy.
    get_receipts: GetReceiptsExchange
