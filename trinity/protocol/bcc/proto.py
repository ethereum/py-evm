from p2p.protocol import Protocol

from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.attestations import Attestation

from trinity.protocol.bcc.commands import (
    Status,
    GetBeaconBlocks,
    BeaconBlocks,
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

from trinity._utils.logging import HasExtendedDebugLogger

if TYPE_CHECKING:
    from .peer import BCCPeer  # noqa: F401


# HasExtendedDebugLogger must come before Protocol so there's self.logger.debug2()
class BCCProtocol(HasExtendedDebugLogger, Protocol):
    name = "bcc"
    version = 0
    _commands = [Status, GetBeaconBlocks, BeaconBlocks, AttestationRecords]
    cmd_length = 4

    peer: "BCCPeer"

    def send_handshake(self, genesis_hash: Hash32, best_hash: Hash32) -> None:
        resp = {
            "protocol_version": self.version,
            "network_id": self.peer.network_id,
            "genesis_hash": genesis_hash,
            "best_hash": best_hash,
        }
        cmd = Status(self.cmd_id_offset)
        self.logger.debug2("Sending BCC/Status msg: %s", resp)
        self.send(*cmd.encode(resp))

    def send_get_blocks(self,
                        block_slot_or_root: Union[BlockNumber, Hash32],
                        max_blocks: int) -> None:
        cmd = GetBeaconBlocks(self.cmd_id_offset)
        data = {
            'block_slot_or_root': block_slot_or_root,
            'max_blocks': max_blocks,
        }
        header, body = cmd.encode(data)
        self.send(header, body)

    def send_blocks(self, blocks: Tuple[BaseBeaconBlock, ...]) -> None:
        cmd = BeaconBlocks(self.cmd_id_offset)
        header, body = cmd.encode(blocks)
        self.send(header, body)

    def send_attestation_records(self, attestations: Tuple[Attestation, ...]) -> None:
        cmd = AttestationRecords(self.cmd_id_offset)
        header, body = cmd.encode(attestations)
        self.send(header, body)
