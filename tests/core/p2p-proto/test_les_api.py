import asyncio

import pytest

from eth.chains.base import MiningChain
from eth.tools.builder.chain import (
    build,
    disable_pow_check,
    genesis,
    latest_mainnet_at,
    mine_block,
)

from trinity.db.eth1.header import AsyncHeaderDB
from trinity.protocol.les.api import LESV1API, LESV2API
from trinity.protocol.les.commands import Announce
from trinity.protocol.les.handshaker import LESHandshakeReceipt
from trinity.protocol.les.payloads import AnnouncePayload
from trinity.protocol.les.proto import BaseLESProtocol, LESProtocolV1, LESProtocolV2
from trinity.tools.factories import (
    ChainContextFactory,
    LESV1PeerPairFactory,
    LESV2PeerPairFactory,
)


@pytest.fixture
def common_base_chain():
    chain = build(
        MiningChain,
        latest_mainnet_at(0),
        disable_pow_check(),
        genesis(),
    )
    return chain


@pytest.fixture(params=(LESV1PeerPairFactory, LESV2PeerPairFactory))
async def alice_and_bob(common_base_chain, request):
    pair_factory = request.param(
        alice_client_version='alice',
        alice_peer_context=ChainContextFactory(headerdb=AsyncHeaderDB(common_base_chain.headerdb.db)),  # noqa: E501
        bob_client_version='bob',
        bob_peer_context=ChainContextFactory(headerdb=AsyncHeaderDB(common_base_chain.headerdb.db)),
    )
    async with pair_factory as (alice, bob):
        yield alice, bob


@pytest.fixture
def alice(alice_and_bob):
    alice, _ = alice_and_bob
    return alice


@pytest.fixture
def bob(alice_and_bob):
    _, bob = alice_and_bob
    return bob


@pytest.fixture
def LESAPI_class(alice):
    if alice.connection.has_protocol(LESProtocolV1):
        return LESV1API
    elif alice.connection.has_protocol(LESProtocolV2):
        return LESV2API
    else:
        raise Exception("No LES protocol found")


@pytest.mark.asyncio
async def test_les_api_properties(alice, LESAPI_class, common_base_chain):
    assert alice.connection.has_logic(LESAPI_class.name)
    les_api = alice.connection.get_logic(LESAPI_class.name, LESAPI_class)

    assert les_api is alice.les_api

    les_receipt = alice.connection.get_receipt_by_type(LESHandshakeReceipt)

    genesis = common_base_chain.headerdb.get_canonical_block_header_by_number(0)
    head = common_base_chain.headerdb.get_canonical_head()

    assert les_api.network_id == les_receipt.network_id
    assert les_api.genesis_hash == les_receipt.genesis_hash
    assert les_api.genesis_hash == genesis.hash

    assert les_api.head_info.head_hash == les_receipt.head_hash
    assert les_api.head_info.head_hash == head.hash
    assert les_api.head_info.head_td == les_receipt.head_td
    assert les_api.head_info.head_number == les_receipt.head_number


@pytest.mark.asyncio
async def test_eth_api_head_info_updates_with_announce(alice, bob, common_base_chain, LESAPI_class):
    # bob mines two blocks on his chain
    got_announce = asyncio.Event()

    async def _handle_announce(connection, msg):
        got_announce.set()

    alice.connection.add_command_handler(Announce, _handle_announce)

    bob_genesis = common_base_chain.headerdb.get_canonical_block_header_by_number(0)

    assert alice.connection.has_logic(LESAPI_class.name)

    les_api = alice.connection.get_logic(LESAPI_class.name, LESAPI_class)

    assert les_api.head_info.head_hash == bob_genesis.hash
    assert les_api.head_info.head_td == bob_genesis.difficulty
    assert les_api.head_info.head_number == 0

    bob_chain = build(
        common_base_chain,
        mine_block(),
        mine_block(),
    )
    head = bob_chain.get_canonical_head()

    les_proto = bob.les_api.protocol
    assert isinstance(les_proto, BaseLESProtocol)
    assert head.block_number == 2
    total_difficulty = bob_chain.headerdb.get_score(head.hash)
    les_proto.send(Announce(AnnouncePayload(
        head_hash=head.hash,
        head_number=head.block_number,
        head_td=total_difficulty,
        reorg_depth=0,
        params=(),
    )))

    await asyncio.wait_for(got_announce.wait(), timeout=1)
    await asyncio.sleep(0.1)

    assert les_api.head_info.head_hash == head.hash
    assert les_api.head_info.head_td == total_difficulty
    assert les_api.head_info.head_number == 2
