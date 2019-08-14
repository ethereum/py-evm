import pytest

from p2p.exceptions import HandshakeFailure

from trinity.tools.bcc_factories import (
    BeaconContextFactory,
    BCCPeerPairFactory,
)


@pytest.mark.asyncio
async def test_unidirectional_handshake():
    alice_context = BeaconContextFactory(client_version_string='alice')
    bob_context = BeaconContextFactory(client_version_string='bob')
    peer_pair = BCCPeerPairFactory(
        alice_peer_context=alice_context,
        bob_peer_context=bob_context,
    )
    async with peer_pair as (alice, bob):
        assert bob.client_version_string == alice_context.client_version_string
        assert alice.client_version_string == bob_context.client_version_string


@pytest.mark.asyncio
async def test_handshake_wrong_network_id():
    alice_context = BeaconContextFactory(network_id=1)
    bob_context = BeaconContextFactory(network_id=2)

    peer_pair = BCCPeerPairFactory(
        alice_peer_context=alice_context,
        bob_peer_context=bob_context,
    )

    with pytest.raises(HandshakeFailure):
        async with peer_pair as (alice, bob):
            pass
