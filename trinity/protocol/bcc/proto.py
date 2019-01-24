from typing import (
    TYPE_CHECKING,
    Tuple,
    Union,
)

from eth_typing import (
    Hash32,
)
from lahja import (
    BroadcastConfig,
)
import ssz

from p2p.kademlia import Node
from p2p.protocol import Protocol

from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.typing import (
    Slot,
)

from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.protocol.bcc.commands import (
    Status,
    StatusMessage,
    GetBeaconBlocks,
    GetBeaconBlocksMessage,
    BeaconBlocks,
    BeaconBlocksMessage,
    NewBeaconBlock,
    NewBeaconBlockMessage,
    Attestations,
    AttestationsMessage,
)
from trinity.protocol.bcc.events import (
    SendBeaconBlocksEvent,
)

from trinity._utils.logging import HasExtendedDebugLogger

if TYPE_CHECKING:
    from .peer import BCCPeer  # noqa: F401


# HasExtendedDebugLogger must come before Protocol so there's self.logger.debug2()
class BCCProtocol(HasExtendedDebugLogger, Protocol):
    name = "bcc"
    version = 0
    _commands = (
        Status,
        GetBeaconBlocks, BeaconBlocks,
        Attestations,
        NewBeaconBlock,
    )
    cmd_length = 5

    peer: "BCCPeer"

    def send_handshake(self,
                       genesis_root: Hash32,
                       head_slot: Slot,
                       network_id: int) -> None:
        resp = StatusMessage(
            protocol_version=self.version,
            network_id=network_id,
            genesis_root=genesis_root,
            head_slot=head_slot,
        )
        cmd = Status(self.cmd_id_offset, self.snappy_support)
        self.logger.debug2("Sending BCC/Status msg: %s", resp)
        self.transport.send(*cmd.encode(resp))

    def send_get_blocks(self,
                        block_slot_or_root: Union[Slot, Hash32],
                        max_blocks: int,
                        request_id: int) -> None:
        cmd = GetBeaconBlocks(self.cmd_id_offset, self.snappy_support)
        header, body = cmd.encode(GetBeaconBlocksMessage(
            request_id=request_id,
            block_slot_or_root=block_slot_or_root,
            max_blocks=max_blocks,
        ))
        self.transport.send(header, body)

    def send_blocks(self, blocks: Tuple[BaseBeaconBlock, ...], request_id: int) -> None:
        cmd = BeaconBlocks(self.cmd_id_offset, self.snappy_support)
        header, body = cmd.encode(BeaconBlocksMessage(
            request_id=request_id,
            encoded_blocks=tuple(ssz.encode(block) for block in blocks),
        ))
        self.transport.send(header, body)

    def send_attestation_records(self, attestations: Tuple[Attestation, ...]) -> None:
        cmd = Attestations(self.cmd_id_offset, self.snappy_support)
        header, body = cmd.encode(AttestationsMessage(
            encoded_attestations=tuple(ssz.encode(attestation) for attestation in attestations)),
        )
        self.transport.send(header, body)

    def send_new_block(self, block: BaseBeaconBlock) -> None:
        cmd = NewBeaconBlock(self.cmd_id_offset, self.snappy_support)
        header, body = cmd.encode(NewBeaconBlockMessage(
            encoded_block=ssz.encode(block),
        ))
        self.transport.send(header, body)


class ProxyBCCProtocol:
    """
    A ``BCCProtocol`` that can be used outside of the process that runs the peer pool. Any
    action performed on this class is delegated to the process that runs the peer pool.
    """

    def __init__(self,
                 remote: Node,
                 event_bus: TrinityEventBusEndpoint,
                 broadcast_config: BroadcastConfig):
        self.remote = remote
        self._event_bus = event_bus
        self._broadcast_config = broadcast_config

    def send_get_blocks(self,
                        block_slot_or_root: Union[Slot, Hash32],
                        max_blocks: int,
                        request_id: int) -> None:
        raise NotImplementedError("Not yet implemented")

    def send_blocks(self, blocks: Tuple[BaseBeaconBlock, ...], request_id: int) -> None:
        self._event_bus.broadcast_nowait(
            SendBeaconBlocksEvent(self.remote, blocks, request_id),
            self._broadcast_config,
        )

    def send_attestation_records(self, attestations: Tuple[Attestation, ...]) -> None:
        raise NotImplementedError("Not yet implemented")

    def send_new_block(self, block: BaseBeaconBlock) -> None:
        raise NotImplementedError("Not yet implemented")
