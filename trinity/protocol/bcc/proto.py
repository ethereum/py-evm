import logging

from p2p.protocol import Protocol

from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.attestations import Attestation

from trinity.protocol.bcc.commands import (
    Status,
    StatusMessage,
    GetBeaconBlocks,
    GetBeaconBlocksMessage,
    BeaconBlocks,
    BeaconBlocksMessage,
    AttestationRecords,
)

from eth_typing import (
    Hash32,
    BlockNumber,
)
from typing import (
    TYPE_CHECKING,
    Tuple,
    Union,
)

if TYPE_CHECKING:
    from .peer import BCCPeer  # noqa: F401


class BCCProtocol(Protocol):
    name = "bcc"
    version = 0
    _commands = [Status, GetBeaconBlocks, BeaconBlocks, AttestationRecords]
    cmd_length = 4
    logger = logging.getLogger("p2p.bcc.BCCProtocol")

    peer: "BCCPeer"

    def send_handshake(self, genesis_hash: Hash32, head_slot: int) -> None:
        resp = StatusMessage(
            protocol_version=self.version,
            network_id=self.peer.network_id,
            genesis_hash=genesis_hash,
            head_slot=head_slot,
        )
        cmd = Status(self.cmd_id_offset)
        self.logger.debug("Sending BCC/Status msg: %s", resp)
        self.send(*cmd.encode(resp))

    def send_get_blocks(self,
                        block_slot_or_root: Union[BlockNumber, Hash32],
                        max_blocks: int,
                        request_id: int) -> None:
        cmd = GetBeaconBlocks(self.cmd_id_offset)
        header, body = cmd.encode(GetBeaconBlocksMessage(
            request_id=request_id,
            block_slot_or_root=block_slot_or_root,
            max_blocks=max_blocks,
        ))
        self.send(header, body)

    def send_blocks(self, blocks: Tuple[BaseBeaconBlock, ...], request_id: int) -> None:
        cmd = BeaconBlocks(self.cmd_id_offset)
        header, body = cmd.encode(BeaconBlocksMessage(
            request_id=request_id,
            blocks=blocks,
        ))
        self.send(header, body)

    def send_attestation_records(self, attestations: Tuple[Attestation, ...]) -> None:
        cmd = AttestationRecords(self.cmd_id_offset)
        header, body = cmd.encode(attestations)
        self.send(header, body)
