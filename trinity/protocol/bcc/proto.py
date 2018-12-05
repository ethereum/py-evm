import logging

from p2p.protocol import Protocol

from trinity.protocol.bcc.commands import (
    Status,
    GetBeaconBlocks,
    BeaconBlocks,
    AttestationRecords,
)


class BCCProtocol(Protocol):
    name = "bcc"
    version = 0
    _commands = [Status, GetBeaconBlocks, BeaconBlocks, AttestationRecords]
    cmd_length = 4
    logger = logging.getLogger("p2p.bcc.BCCProtocol")
