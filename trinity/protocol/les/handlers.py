from trinity.protocol.common.handlers import (
    BaseRequestResponseHandler,
)

from .managers import GetBlockHeadersRequestManager


class LESRequestResponseHandler(BaseRequestResponseHandler):
    _managers = {
        'get_block_headers': GetBlockHeadersRequestManager,
    }

    get_block_headers: GetBlockHeadersRequestManager
