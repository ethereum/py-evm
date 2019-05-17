from cancel_token import CancelToken

from p2p.service import BaseService

from trinity.endpoint import (
    TrinityEventBusEndpoint,
)

from .tracker import (
    BaseEth1PeerTracker,
)
from .events import (
    TrackPeerEvent,
    GetPeerCandidatesRequest,
    GetPeerCandidatesResponse,
)


class PeerDBServer(BaseService):
    """
    Server to handle the event bus communication for PeerDB
    """

    def __init__(self,
                 event_bus: TrinityEventBusEndpoint,
                 tracker: BaseEth1PeerTracker,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.tracker = tracker
        self.event_bus = event_bus

    async def handle_track_peer_event(self) -> None:
        async for command in self.wait_iter(self.event_bus.stream(TrackPeerEvent)):
            self.tracker.track_peer_connection(
                command.remote,
                command.is_outbound,
                command.last_connected_at,
                command.genesis_hash,
                command.protocol,
                command.protocol_version,
                command.network_id,
            )

    async def handle_get_peer_candidates_request(self) -> None:
        async for req in self.wait_iter(self.event_bus.stream(GetPeerCandidatesRequest)):
            candidates = tuple(await self.tracker.get_peer_candidates(
                req.num_requested,
                req.connected_remotes,
            ))
            await self.event_bus.broadcast(
                GetPeerCandidatesResponse(candidates),
                req.broadcast_config(),
            )

    async def _run(self) -> None:
        self.logger.debug("Running PeerDBServer")

        self.run_daemon_task(self.handle_track_peer_event())
        self.run_daemon_task(self.handle_get_peer_candidates_request())

        await self.cancel_token.wait()
