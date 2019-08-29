import logging
from typing import (
    NamedTuple,
)

from trio.abc import (
    ReceiveChannel,
)

from eth_utils import (
    encode_hex,
)
from eth_utils.toolz import (
    merge,
)

from p2p.trio_service import (
    Service,
)

from p2p.discv5.abc import (
    EnrDbApi,
)
from p2p.discv5.channel_services import (
    Endpoint,
)
from p2p.discv5.constants import (
    IP_V4_ADDRESS_ENR_KEY,
    UDP_PORT_ENR_KEY,
)
from p2p.discv5.enr import (
    UnsignedENR,
)
from p2p.discv5.identity_schemes import (
    IdentitySchemeRegistry,
)
from p2p.discv5.typing import (
    NodeID,
)


class EndpointVote(NamedTuple):
    endpoint: Endpoint
    node_id: NodeID
    timestamp: float


class EndpointTracker(Service):

    logger = logging.getLogger("p2p.discv5.endpoint_tracker.EndpointTracker")

    def __init__(self,
                 local_private_key: bytes,
                 local_node_id: NodeID,
                 enr_db: EnrDbApi,
                 identity_scheme_registry: IdentitySchemeRegistry,
                 vote_receive_channel: ReceiveChannel[EndpointVote],
                 ) -> None:
        self.local_private_key = local_private_key
        self.local_node_id = local_node_id
        self.enr_db = enr_db
        self.identity_scheme_registry = identity_scheme_registry

        self.vote_receive_channel = vote_receive_channel

    async def run(self) -> None:
        async with self.vote_receive_channel:
            async for vote in self.vote_receive_channel:
                await self.handle_vote(vote)

    async def handle_vote(self, vote: EndpointVote) -> None:
        self.logger.debug(
            "Received vote for %s from %s",
            vote.endpoint,
            encode_hex(vote.node_id),
        )

        current_enr = await self.enr_db.get(self.local_node_id)

        # TODO: majority voting, discard old votes
        are_endpoint_keys_present = (
            IP_V4_ADDRESS_ENR_KEY in current_enr and
            UDP_PORT_ENR_KEY in current_enr
        )
        enr_needs_update = not are_endpoint_keys_present or (
            vote.endpoint.ip_address != current_enr[IP_V4_ADDRESS_ENR_KEY] and
            vote.endpoint.port != current_enr[UDP_PORT_ENR_KEY]
        )
        if enr_needs_update:
            kv_pairs = merge(
                current_enr,
                {
                    IP_V4_ADDRESS_ENR_KEY: vote.endpoint.ip_address,
                    UDP_PORT_ENR_KEY: vote.endpoint.port,
                }
            )
            new_unsigned_enr = UnsignedENR(
                kv_pairs=kv_pairs,
                sequence_number=current_enr.sequence_number + 1,
                identity_scheme_registry=self.identity_scheme_registry,
            )
            signed_enr = new_unsigned_enr.to_signed_enr(self.local_private_key)
            self.logger.info(
                f"Updating local endpoint to %s (new ENR sequence number: %d)",
                vote.endpoint,
                signed_enr.sequence_number,
            )
            await self.enr_db.update(signed_enr)
