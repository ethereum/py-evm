from eth_keys import datatypes

from trinity.protocol.bcc_libp2p.utils import (
    peer_id_from_pubkey,
)

from libp2p.peer.id import (
    id_b58_decode,
)


def test_peer_id_from_pubkey():
    pubkey = datatypes.PublicKey(
        b'n\x85UD\xe9^\xbfo\x05\xd1z\xbd\xe5k\x87Y\xe9\xfa\xb3z:\xf8z\xc5\xd7K\xa6\x00\xbbc\xda4M\x10\x1cO\x88\tl\x82\x7f\xd7\xec6\xd8\xdc\xe2\x9c\xdcG\xa5\xea|\x9e\xc57\xf8G\xbe}\xfa\x10\xe9\x12'  # noqa: E501
    )
    peer_id_expected = id_b58_decode("QmQiv6sR3qHqhUVgC5qUBVWi8YzM6HknYbu4oQKVAqPCGF")
    assert peer_id_from_pubkey(pubkey) == peer_id_expected
