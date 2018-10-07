from trinity.protocol.common.handlers import (
    BaseChainExchangeHandler,
)

from .exchanges import (
    GetBlockBodiesExchange,
    GetBlockHeadersExchange,
)


class ETHExchangeHandler(BaseChainExchangeHandler):
    _exchange_config = {
        'get_block_bodies': GetBlockBodiesExchange,
        'get_block_headers': GetBlockHeadersExchange,
    }

    # These are needed only to please mypy.
    get_block_bodies: GetBlockBodiesExchange
