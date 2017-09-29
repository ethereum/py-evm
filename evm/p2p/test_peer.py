from evm.p2p.les import LESProtocol
from evm.p2p.peer import Peer
from evm.p2p.protocol import Protocol
from evm.p2p.p2p_proto import P2PProtocol


def test_sub_protocol_matching():
    peer = ProtoMatchingPeer([LESProtocol, LESProtocolV2, ETHProtocol63])

    peer.match_protocols([
        (LESProtocol.name, LESProtocol.version),
        (LESProtocolV2.name, LESProtocolV2.version),
        (LESProtocolV3.name, LESProtocolV3.version),
        (ETHProtocol63.name, ETHProtocol63.version),
        ('unknown', 1),
    ])

    assert len(peer.sub_protocols) == 2
    eth_proto, les_proto = peer.sub_protocols
    assert isinstance(eth_proto, ETHProtocol63)
    assert eth_proto.cmd_id_offset == peer.base_protocol.cmd_length

    assert isinstance(les_proto, LESProtocolV2)
    assert les_proto.cmd_id_offset == peer.base_protocol.cmd_length + eth_proto.cmd_length


class LESProtocolV2(LESProtocol):
    version = 2


class LESProtocolV3(LESProtocol):
    version = 3


class ETHProtocol63(Protocol):
    name = b'eth'
    version = 63
    cmd_length = 15


class ProtoMatchingPeer(Peer):

    def __init__(self, available_sub_protocols):
        self._available_sub_protocols = available_sub_protocols
        self.base_protocol = P2PProtocol(self)
        self.sub_protocols = []
