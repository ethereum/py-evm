import pytest

from trinity.tools.bcc_factories import ConnectionPairFactory


@pytest.mark.asyncio
async def test_connection_factory_with_Libp2pPeer():
    async with ConnectionPairFactory() as (alice, bob):
        assert bob.peer_id in alice.handshaked_peers
        assert alice.peer_id in bob.handshaked_peers
