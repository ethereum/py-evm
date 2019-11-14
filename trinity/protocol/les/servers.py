from typing import Any

from cancel_token import CancelToken
from lahja import (
    BroadcastConfig,
    EndpointAPI,
)

from p2p.abc import CommandAPI, SessionAPI

from trinity.db.eth1.header import BaseAsyncHeaderDB
from trinity.protocol.common.servers import (
    BaseIsolatedRequestServer,
    BasePeerRequestHandler,
)
from trinity.protocol.les import commands
from trinity.protocol.les.events import GetBlockHeadersEvent
from trinity.protocol.les.peer import (
    LESProxyPeer,
)


class LESPeerRequestHandler(BasePeerRequestHandler):
    async def handle_get_block_headers(self,
                                       peer: LESProxyPeer,
                                       cmd: commands.GetBlockHeaders) -> None:

        self.logger.debug("Peer %s made header request: %s", peer, cmd)
        headers = await self.lookup_headers(cmd.payload.query)
        self.logger.debug2("Replying to %s with %d headers", peer, len(headers))
        peer.les_api.send_block_headers(headers, request_id=cmd.payload.request_id)


class LightRequestServer(BaseIsolatedRequestServer):
    """
    Monitor commands from peers, to identify inbound requests that should receive a response.
    Handle those inbound requests by querying our local database and replying.
    """

    def __init__(
            self,
            event_bus: EndpointAPI,
            broadcast_config: BroadcastConfig,
            db: BaseAsyncHeaderDB,
            token: CancelToken = None) -> None:
        super().__init__(
            event_bus,
            broadcast_config,
            (GetBlockHeadersEvent,),
            token,
        )
        self._handler = LESPeerRequestHandler(db, self.cancel_token)

    async def _handle_msg(self,
                          session: SessionAPI,
                          cmd: CommandAPI[Any]) -> None:

        self.logger.debug2("Peer %s requested %s", session, cmd)
        peer = LESProxyPeer.from_session(session, self.event_bus, self.broadcast_config)
        if isinstance(cmd, commands.GetBlockHeaders):
            await self._handler.handle_get_block_headers(peer, cmd)
        else:
            self.logger.debug("%s msg not handled yet, needs to be implemented", cmd)
