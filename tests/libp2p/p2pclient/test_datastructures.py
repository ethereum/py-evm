import pytest

from multiaddr import (
    Multiaddr,
)

from libp2p.p2pclient.p2pclient import (
    PeerID,
    PeerInfo,
    StreamInfo,
)

import libp2p.p2pclient.pb.p2pd_pb2 as p2pd_pb


@pytest.fixture('module')
def peer_id_string():
    return "QmS5QmciTXXnCUCyxud5eWFenUMAmvAWSDa1c7dvdXRMZ7"


@pytest.fixture('module')
def peer_id_bytes():
    return b'\x12 7\x87F.[\xb5\xb1o\xe5*\xc7\xb9\xbb\x11:"Z|j2\x8ad\x1b\xa6\xe5<Ip\xfe\xb4\xf5v'


@pytest.fixture('module')
def peer_id(peer_id_bytes):
    return PeerID(peer_id_bytes)


@pytest.fixture('module')
def maddr():
    return Multiaddr('/unix/123')


def test_peer_id(peer_id_string, peer_id_bytes, peer_id):
    # test initialized with bytes
    assert peer_id.to_bytes() == peer_id_bytes
    assert peer_id.to_string() == peer_id_string
    # test initialized with string
    peer_id_2 = PeerID.from_base58(peer_id_string)
    assert peer_id_2.to_bytes() == peer_id_bytes
    assert peer_id_2.to_string() == peer_id_string
    # test equal
    assert peer_id == peer_id_2
    # test not equal
    peer_id_3 = PeerID.from_base58("QmbmfNDEth7Ucvjuxiw3SP3E4PoJzbk7g4Ge6ZDigbCsNp")
    assert peer_id != peer_id_3


def test_stream_info(peer_id, maddr):
    proto = '123'
    # test case: `StreamInfo.__init__`
    si = StreamInfo(peer_id, maddr, proto)
    assert si.peer_id == peer_id
    assert si.addr == maddr
    assert si.proto == proto
    # test case: `StreamInfo.to_pb`
    pb_si = si.to_pb()
    assert pb_si.peer == peer_id.to_bytes()
    assert pb_si.addr == maddr.to_bytes()
    assert pb_si.proto == si.proto
    # test case: `StreamInfo.from_pb`
    si_1 = StreamInfo.from_pb(pb_si)
    assert si_1.peer_id == peer_id
    assert si_1.addr == maddr
    assert si_1.proto == proto


def test_peer_info(peer_id, maddr):
    pi = PeerInfo(peer_id, [maddr])
    # test case: `PeerInfo.__init__`
    assert pi.peer_id == peer_id
    assert pi.addrs == [maddr]
    # test case: `PeerInfo.from_pb`
    pi_pb = p2pd_pb.PeerInfo(
        id=peer_id.to_bytes(),
        addrs=[maddr.to_bytes()],
    )
    pi_1 = PeerInfo.from_pb(pi_pb)
    assert pi.peer_id == pi_1.peer_id
    assert pi.addrs == pi_1.addrs
