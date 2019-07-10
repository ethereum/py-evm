from typing import (
    Any,
    List,
)

import base58

from multiaddr import (
    Multiaddr,
)

from .pb import p2pd_pb2


class PeerID:
    _bytes: bytes

    def __init__(self, peer_id_bytes: bytes) -> None:
        # TODO: should add checks for the validity of peer_id
        self._bytes = peer_id_bytes

    def __eq__(self, other: Any) -> bool:
        return self._bytes == other._bytes

    def __ne__(self, other: Any) -> bool:
        return not (self == other)

    def __repr__(self) -> str:
        return f"<PeerID {self.to_string()[2:10]}>"

    def to_bytes(self) -> bytes:
        return self._bytes

    def to_string(self) -> str:
        return base58.b58encode(self._bytes).decode()

    @classmethod
    def from_base58(cls, peer_id_string: str) -> 'PeerID':
        peer_id_bytes = base58.b58decode(peer_id_string)
        pid = PeerID(peer_id_bytes)
        return pid


class StreamInfo:
    peer_id: PeerID
    addr: Multiaddr
    proto: str

    def __init__(self, peer_id: PeerID, addr: Multiaddr, proto: str) -> None:
        self.peer_id = peer_id
        self.addr = addr
        self.proto = proto

    def __repr__(self) -> str:
        return f"<StreamInfo peer_id={self.peer_id} addr={self.addr} proto={self.proto}>"

    def to_pb(self) -> p2pd_pb2.StreamInfo:
        pb_msg = p2pd_pb2.StreamInfo(
            peer=self.peer_id.to_bytes(),
            addr=self.addr.to_bytes(),
            proto=self.proto,
        )
        return pb_msg

    @classmethod
    def from_pb(cls, pb_msg: p2pd_pb2.StreamInfo) -> 'StreamInfo':
        stream_info = cls(
            peer_id=PeerID(pb_msg.peer),
            addr=Multiaddr(pb_msg.addr),
            proto=pb_msg.proto,
        )
        return stream_info


class PeerInfo:
    peer_id: PeerID
    addrs: List[Multiaddr]

    def __init__(self, peer_id: PeerID, addrs: List[Multiaddr]):
        self.peer_id = peer_id
        self.addrs = addrs

    def __repr__(self) -> str:
        return f"<PeerInfo peer_id={self.peer_id} addrs={self.addrs}>"

    @classmethod
    def from_pb(cls, peer_info_pb: p2pd_pb2.PeerInfo) -> 'PeerInfo':
        peer_id = PeerID(peer_info_pb.id)
        addrs = [Multiaddr(addr) for addr in peer_info_pb.addrs]
        return cls(peer_id, addrs)
