from libp2p.p2pclient.p2pclient import (
    PeerID,
)


def test_peer_id():
    peer_id_string = "QmS5QmciTXXnCUCyxud5eWFenUMAmvAWSDa1c7dvdXRMZ7"
    peer_id_bytes = b'\x12 7\x87F.[\xb5\xb1o\xe5*\xc7\xb9\xbb\x11:"Z|j2\x8ad\x1b\xa6\xe5<Ip\xfe\xb4\xf5v'  # noqa: E501
    # test initialized with bytes
    peer_id = PeerID(peer_id_bytes)
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
