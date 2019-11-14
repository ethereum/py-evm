from typing import (
    Sequence,
)

from eth.abc import BlockHeaderAPI
from eth_utils import get_extended_debug_logger
from lahja import (
    BroadcastConfig,
    EndpointAPI,
)

from p2p.abc import SessionAPI

from trinity._utils.les import (
    gen_request_id,
)
from trinity._utils.errors import (
    SupportsError,
)

from .commands import (
    BlockHeaders,
)
from .events import (
    SendBlockHeadersEvent,
)
from .payloads import (
    BlockHeadersPayload,
)


class ProxyLESAPI:
    """
    An ``LESAPI`` that can be used outside of the process that runs the peer pool. Any
    action performed on this class is delegated to the process that runs the peer pool.
    """
    logger = get_extended_debug_logger('trinity.protocol.les.proxy.ProxyLESAPI')

    def __init__(self,
                 session: SessionAPI,
                 event_bus: EndpointAPI,
                 broadcast_config: BroadcastConfig):
        self.session = session
        self._event_bus = event_bus
        self._broadcast_config = broadcast_config

    def raise_if_needed(self, value: SupportsError) -> None:
        if value.error is not None:
            self.logger.warning(
                "Raised %s while fetching from peer %s", value.error, self.session,
            )
            raise value.error

    def send_block_headers(self,
                           headers: Sequence[BlockHeaderAPI],
                           buffer_value: int = 0,
                           request_id: int = None) -> int:
        if request_id is None:
            request_id = gen_request_id()
        command = BlockHeaders(BlockHeadersPayload(
            request_id=request_id,
            buffer_value=buffer_value,
            headers=tuple(headers),
        ))
        self._event_bus.broadcast_nowait(
            SendBlockHeadersEvent(self.session, command),
            self._broadcast_config,
        )
        return command.payload.request_id
