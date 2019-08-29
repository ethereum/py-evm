import pytest

import trio

from trio.testing import (
    wait_all_tasks_blocked,
)

import pytest_trio

from p2p.trio_service import (
    background_service,
)

from p2p.tools.factories.discovery import (
    EndpointFactory,
    EndpointVoteFactory,
    ENRFactory,
)
from p2p.tools.factories.keys import (
    PrivateKeyFactory,
)

from p2p.discv5.constants import (
    IP_V4_ADDRESS_ENR_KEY,
    UDP_PORT_ENR_KEY,
)
from p2p.discv5.endpoint_tracker import (
    EndpointTracker,
)
from p2p.discv5.enr_db import (
    MemoryEnrDb,
)
from p2p.discv5.identity_schemes import (
    default_identity_scheme_registry,
)


@pytest.fixture
def private_key():
    return PrivateKeyFactory().to_bytes()


@pytest.fixture
def initial_enr(private_key):
    return ENRFactory(
        private_key=private_key,
    )


@pytest_trio.trio_fixture
async def enr_db(initial_enr):
    enr_db = MemoryEnrDb(default_identity_scheme_registry)
    await enr_db.insert(initial_enr)
    return enr_db


@pytest.fixture
def vote_channels():
    return trio.open_memory_channel(0)


@pytest.fixture
async def endpoint_tracker(private_key, initial_enr, enr_db, vote_channels):
    endpoint_tracker = EndpointTracker(
        local_private_key=private_key,
        local_node_id=initial_enr.node_id,
        enr_db=enr_db,
        identity_scheme_registry=default_identity_scheme_registry,
        vote_receive_channel=vote_channels[1],
    )
    async with background_service(endpoint_tracker):
        yield endpoint_tracker


@pytest.mark.trio
async def test_endpoint_tracker_updates_enr(endpoint_tracker, initial_enr, enr_db, vote_channels):
    endpoint = EndpointFactory()
    endpoint_vote = EndpointVoteFactory(endpoint=endpoint)
    await vote_channels[0].send(endpoint_vote)
    await wait_all_tasks_blocked()  # wait until vote has been processed

    updated_enr = await enr_db.get(initial_enr.node_id)
    assert updated_enr.sequence_number == initial_enr.sequence_number + 1
    assert updated_enr[IP_V4_ADDRESS_ENR_KEY] == endpoint.ip_address
    assert updated_enr[UDP_PORT_ENR_KEY] == endpoint.port
