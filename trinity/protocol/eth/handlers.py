from trinity.protocol.common.handlers import (
    BaseRequestResponseHandler,
)

from .managers import (
    GetBlockBodiesRequestManager,
    GetBlockHeadersRequestManager,
    GetNodeDataRequestManager,
    GetReceiptsRequestManager,
)


class ETHRequestResponseHandler(BaseRequestResponseHandler):
    _managers = {
        'get_block_bodies': GetBlockBodiesRequestManager,
        'get_block_headers': GetBlockHeadersRequestManager,
        'get_node_data': GetNodeDataRequestManager,
        'get_receipts': GetReceiptsRequestManager,
    }

    # These are needed only to please mypy.
    get_block_bodies: GetBlockBodiesRequestManager
    get_block_headers: GetBlockHeadersRequestManager
    get_node_data: GetNodeDataRequestManager
    get_receipts: GetReceiptsRequestManager
