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

from trinity._utils.assertions import assert_type_equality
from trinity.db.eth1.header import AsyncHeaderDB
from trinity.protocol.eth.api import ETHAPI
from trinity.protocol.eth.commands import (
    GetBlockHeaders,
    GetNodeData,
    NewBlock,
    Status,
)
from trinity.protocol.eth.handshaker import ETHHandshakeReceipt

from trinity.tools.factories.common import (
    BlockHeadersQueryFactory,
)
from trinity.tools.factories.eth import (
    StatusPayloadFactory,
)
from trinity.tools.factories import (
    BlockHashFactory,
    ChainContextFactory,
    ETHPeerPairFactory,
)


@pytest.fixture
def bob_chain():
    chain = build(
        MiningChain,
        latest_mainnet_at(0),
        disable_pow_check(),
        genesis(),
    )
    return chain


@pytest.fixture
def alice_chain(bob_chain):
    bob_genesis = bob_chain.headerdb.get_canonical_block_header_by_number(0)

    chain = build(
        MiningChain,
        latest_mainnet_at(0),
        disable_pow_check(),
        genesis(params={"timestamp": bob_genesis.timestamp}),
    )
    return chain


@pytest.fixture
async def alice_and_bob(alice_chain, bob_chain):
    pair_factory = ETHPeerPairFactory(
        alice_client_version='alice',
        alice_peer_context=ChainContextFactory(headerdb=AsyncHeaderDB(alice_chain.headerdb.db)),
        bob_client_version='bob',
        bob_peer_context=ChainContextFactory(headerdb=AsyncHeaderDB(bob_chain.headerdb.db)),
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


@pytest.mark.asyncio
async def test_eth_api_properties(alice):
    assert alice.connection.has_logic(ETHAPI.name)
    eth_api = alice.connection.get_logic(ETHAPI.name, ETHAPI)

    assert eth_api is alice.eth_api

    eth_receipt = alice.connection.get_receipt_by_type(ETHHandshakeReceipt)

    assert eth_api.network_id == eth_receipt.network_id
    assert eth_api.genesis_hash == eth_receipt.genesis_hash

    assert eth_api.head_info.head_hash == eth_receipt.head_hash
    assert eth_api.head_info.head_td == eth_receipt.total_difficulty
    assert not hasattr(eth_api, 'head_number')


@pytest.mark.asyncio
async def test_eth_api_head_info_updates_with_newblock(alice, bob, bob_chain):
    # mine two blocks on bob's chain
    bob_chain = build(
        bob_chain,
        mine_block(),
        mine_block(),
    )

    got_new_block = asyncio.Event()

    async def _handle_new_block(connection, msg):
        got_new_block.set()

    alice.connection.add_command_handler(NewBlock, _handle_new_block)

    bob_genesis = bob_chain.headerdb.get_canonical_block_header_by_number(0)

    bob_eth_api = bob.connection.get_logic(ETHAPI.name, ETHAPI)
    alice_eth_api = alice.connection.get_logic(ETHAPI.name, ETHAPI)

    assert alice_eth_api.head_info.head_hash == bob_genesis.hash
    assert alice_eth_api.head_info.head_td == bob_genesis.difficulty
    assert not hasattr(alice_eth_api.head_info, 'head_number')

    head = bob_chain.get_canonical_head()
    assert head.block_number == 2
    head_block = bob_chain.get_block_by_header(head)
    total_difficulty = bob_chain.headerdb.get_score(head.hash)

    bob_eth_api.send_new_block(
        head_block,
        total_difficulty,
    )

    await asyncio.wait_for(got_new_block.wait(), timeout=1)

    assert alice_eth_api.head_info.head_hash == head.parent_hash
    assert alice_eth_api.head_info.head_td == bob_chain.headerdb.get_score(head.parent_hash)
    assert alice_eth_api.head_info.head_number == 1


@pytest.mark.asyncio
async def test_eth_api_send_status(alice, bob):
    payload = StatusPayloadFactory()

    command_fut = asyncio.Future()

    async def _handle_cmd(connection, cmd):
        command_fut.set_result(cmd)

    bob.connection.add_command_handler(Status, _handle_cmd)
    alice.eth_api.send_status(payload)

    result = await asyncio.wait_for(command_fut, timeout=1)
    assert isinstance(result, Status)
    assert_type_equality(payload, result.payload)


@pytest.mark.asyncio
async def test_eth_api_send_get_node_data(alice, bob):
    payload = tuple(BlockHashFactory.create_batch(5))

    command_fut = asyncio.Future()

    async def _handle_cmd(connection, cmd):
        command_fut.set_result(cmd)

    bob.connection.add_command_handler(GetNodeData, _handle_cmd)
    alice.eth_api.send_get_node_data(payload)

    result = await asyncio.wait_for(command_fut, timeout=1)
    assert isinstance(result, GetNodeData)
    assert_type_equality(payload, result.payload)


@pytest.mark.asyncio
async def test_eth_api_send_get_block_headers(alice, bob):
    payload = BlockHeadersQueryFactory()

    command_fut = asyncio.Future()

    async def _handle_cmd(connection, cmd):
        command_fut.set_result(cmd)

    bob.connection.add_command_handler(GetBlockHeaders, _handle_cmd)
    alice.eth_api.send_get_block_headers(
        block_number_or_hash=payload.block_number_or_hash,
        max_headers=payload.block_number_or_hash,
        skip=payload.skip,
        reverse=payload.reverse,
    )

    result = await asyncio.wait_for(command_fut, timeout=1)
    assert isinstance(result, GetBlockHeaders)
    assert_type_equality(payload, result.payload)
