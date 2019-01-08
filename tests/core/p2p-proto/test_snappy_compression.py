import pytest

from tests.core.peer_helpers import (
    get_directly_linked_peers,
    get_directly_linked_v4_and_v5_peers,
)


@pytest.mark.asyncio
async def test_snappy_compression_enabled_between_connected_v5_protocol_peers(request, event_loop):
    alice, bob = await get_directly_linked_peers(request, event_loop)
    assert alice.sub_proto.snappy_support is True
    assert alice.sub_proto.snappy_support is True


@pytest.mark.asyncio
async def test_snappy_compression_enabled_between_connected_v4_and_v5_protocol_peers(
        request,
        event_loop):
    alice, bob = await get_directly_linked_v4_and_v5_peers(request, event_loop)
    assert alice.sub_proto.snappy_support is False
    assert alice.sub_proto.snappy_support is False
