from trinity.protocol.common.handlers import (
    BaseRequestResponseHandler,
)

from .managers import GetBlockHeadersRequestManager


class ETHRequestResponseHandler(BaseRequestResponseHandler):
    _managers = {
        'get_block_headers': GetBlockHeadersRequestManager,
    }

    get_block_headers: GetBlockHeadersRequestManager
