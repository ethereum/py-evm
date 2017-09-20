from evm.p2p.protocol import (
    Protocol,
)


class LESProtocol(Protocol):
    name = b'les'
    version = 1
    commands = []
