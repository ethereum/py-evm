from trinity.protocol.bcc_libp2p.utils import (
    peer_id_from_pubkey,
)


def test_peer_id_from_pubkey(privkey):
    peer_id = peer_id_from_pubkey(privkey.public_key)
    assert peer_id != ""
