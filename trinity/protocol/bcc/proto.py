from typing import (
    TYPE_CHECKING,
    Tuple,
    Union,
)

from eth_typing import (
    Hash32,
)

import ssz

from p2p.protocol import Protocol

from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.typing import (
    Slot,
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
