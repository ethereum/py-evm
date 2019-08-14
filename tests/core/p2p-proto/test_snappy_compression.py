import pytest

from p2p.tools.paragon import ParagonContext
from p2p.tools.factories import ParagonPeerPairFactory


@pytest.mark.asyncio
async def test_snappy_compression_enabled_between_connected_v5_protocol_peers():
    async with ParagonPeerPairFactory() as (alice, bob):
        assert alice.sub_proto.snappy_support is True
        assert alice.sub_proto.snappy_support is True


@pytest.mark.asyncio
async def test_snappy_compression_enabled_between_connected_v4_and_v5_protocol_peers():
    bob_context = ParagonContext(p2p_version=4)
    async with ParagonPeerPairFactory(bob_peer_context=bob_context) as (alice, bob):
        assert alice.sub_proto.snappy_support is False
        assert alice.sub_proto.snappy_support is False
