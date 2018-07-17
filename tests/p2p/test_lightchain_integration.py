import asyncio
import logging

import pytest
import rlp
from eth_utils import (
    decode_hex,
    encode_hex,
)

from eth_hash.auto import keccak

from eth.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
    ROPSTEN_GENESIS_HEADER,
    ROPSTEN_VM_CONFIGURATION,
)
from eth.db.backends.memory import MemoryDB

from p2p import ecies
from p2p.chain import LightChainSyncer
from p2p.kademlia import Node
from p2p.lightchain import LightPeerChain
from p2p.peer import LESPeer, PeerPool

from integration_test_helpers import (
    FakeAsyncChainDB,
    FakeAsyncRopstenChain,
    FakeAsyncHeaderDB,
    connect_to_peers_loop,
)


@pytest.mark.asyncio
async def test_lightchain_integration(request, event_loop, caplog):
    """Test LightChainSyncer/LightPeerChain against a running geth instance.

    In order to run this you need to pass the following to pytest:

        pytest --integration --capture=no --enode=...

    If you don't have any geth testnet data ready, it is very quick to generate some with:

        geth --testnet --syncmode full

    You only need the first 11 blocks for this test to succeed. Then you can restart geth with:

        geth --testnet --lightserv 90 --nodiscover
    """
    # TODO: Implement a pytest fixture that runs geth as above, so that we don't need to run it
    # manually.
    if not pytest.config.getoption("--integration"):
        pytest.skip("Not asked to run integration tests")

    # will almost certainly want verbose logging in a failure
    caplog.set_level(logging.DEBUG)

    remote = Node.from_uri(pytest.config.getoption("--enode"))
    base_db = MemoryDB()
    chaindb = FakeAsyncChainDB(base_db)
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    headerdb = FakeAsyncHeaderDB(base_db)
    peer_pool = PeerPool(
        LESPeer,
        FakeAsyncHeaderDB(base_db),
        ROPSTEN_NETWORK_ID,
        ecies.generate_privkey(),
        ROPSTEN_VM_CONFIGURATION,
    )
    chain = FakeAsyncRopstenChain(base_db)
    syncer = LightChainSyncer(chain, chaindb, peer_pool)
    syncer.min_peers_to_sync = 1
    peer_chain = LightPeerChain(headerdb, peer_pool)

    asyncio.ensure_future(peer_pool.run())
    asyncio.ensure_future(connect_to_peers_loop(peer_pool, tuple([remote])))
    asyncio.ensure_future(peer_chain.run())
    asyncio.ensure_future(syncer.run())
    await asyncio.sleep(0)  # Yield control to give the LightChainSyncer a chance to start

    def finalizer():
        event_loop.run_until_complete(peer_pool.cancel())
        event_loop.run_until_complete(peer_chain.cancel())
        event_loop.run_until_complete(syncer.cancel())

    request.addfinalizer(finalizer)

    n = 11

    # Wait for the chain to sync a few headers.
    async def wait_for_header_sync(block_number):
        while headerdb.get_canonical_head().block_number < block_number:
            await asyncio.sleep(0.1)
    await asyncio.wait_for(wait_for_header_sync(n), 5)

    # https://ropsten.etherscan.io/block/11
    header = headerdb.get_canonical_block_header_by_number(n)
    body = await peer_chain.get_block_body_by_hash(header.hash)
    assert len(body['transactions']) == 15

    receipts = await peer_chain.get_receipts(header.hash)
    assert len(receipts) == 15
    assert encode_hex(keccak(rlp.encode(receipts[0]))) == (
        '0xf709ed2c57efc18a1675e8c740f3294c9e2cb36ba7bb3b89d3ab4c8fef9d8860')

    assert len(peer_pool) == 1
    head_info = peer_pool.highest_td_peer.head_info
    head = await peer_chain.get_block_header_by_hash(head_info.block_hash)
    assert head.block_number == head_info.block_number

    # In order to answer queries for contract code, geth needs the state trie entry for the block
    # we specify in the query, but because of fast sync we can only assume it has that for recent
    # blocks, so we use the current head to lookup the code for the contract below.
    # https://ropsten.etherscan.io/address/0x95a48dca999c89e4e284930d9b9af973a7481287
    contract_addr = decode_hex('0x8B09D9ac6A4F7778fCb22852e879C7F3B2bEeF81')
    contract_code = await peer_chain.get_contract_code(head.hash, contract_addr)
    assert encode_hex(contract_code) == '0x600060006000600060006000356000f1'

    account = await peer_chain.get_account(head.hash, contract_addr)
    assert account.code_hash == keccak(contract_code)
    assert account.balance == 0
