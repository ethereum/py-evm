import pytest

from p2p.ecies import (
    generate_privkey,
)

from trinity.protocol.bcc_libp2p.utils import (
    peer_id_from_pubkey,
)


@pytest.fixture
def privkey():
    return generate_privkey()


@pytest.fixture
def peer_id(privkey):
    return peer_id_from_pubkey(privkey.public_key)
