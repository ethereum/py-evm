import asyncio

import pytest
import rlp
from eth_keys import keys
from eth_utils import (
    decode_hex,
    encode_hex,
)

from evm.chains.ropsten import ROPSTEN_NETWORK_ID, ROPSTEN_GENESIS_HEADER
from evm.chains.mainnet import MAINNET_VM_CONFIGURATION
from evm.db.backends.memory import MemoryDB
from evm.db.chain import BaseChainDB
from evm.utils.keccak import keccak
from evm.vm.forks.frontier import FrontierBlock

from evm.p2p import ecies
from evm.p2p import kademlia
from evm.p2p.lightchain import LightChain
from evm.p2p.peer import PeerPool


class LocalGethPeerPool(PeerPool):
    min_peers = 1

    async def get_nodes_to_connect(self):
        nodekey = keys.PrivateKey(decode_hex(
            "45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8"))
        remoteid = nodekey.public_key.to_hex()
        return [
            kademlia.Node(
                keys.PublicKey(decode_hex(remoteid)),
                kademlia.Address('127.0.0.1', 30303, 30303))
        ]


IntegrationTestLightChain = LightChain.configure(
    name='IntegrationTest LightChain',
    privkey=ecies.generate_privkey(),
    vm_configuration=MAINNET_VM_CONFIGURATION,
    network_id=ROPSTEN_NETWORK_ID,
    peer_pool_class=LocalGethPeerPool,
    max_consecutive_timeouts=1,
)


@pytest.mark.asyncio
async def test_lightchain_integration(request, event_loop):
    """Test LightChain against a local geth instance.

    This test assumes a geth/ropsten instance is listening on 127.0.0.1:30303 and serving light
    clients. In order to achieve that, simply run it with the following command line:

        $ geth -nodekeyhex 45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8 \
               -testnet -lightserv 90
    """
    # TODO: Implement a pytest fixture that runs geth as above, so that we don't need to run it
    # manually.
    if not pytest.config.getoption("--integration"):
        pytest.skip("Not asked to run integration tests")

    chaindb = BaseChainDB(MemoryDB())
    chaindb.persist_header_to_db(ROPSTEN_GENESIS_HEADER)
    chain = IntegrationTestLightChain(chaindb)
    asyncio.ensure_future(chain.run())
    await asyncio.sleep(0)  # Yield control to give the LightChain a chance to start

    def finalizer():
        event_loop.run_until_complete(chain.stop())

    request.addfinalizer(finalizer)

    n = 11

    # Wait for the chain to sync a few headers.
    async def wait_for_header_sync(block_number):
        while chaindb.get_canonical_head().block_number < block_number:
            await asyncio.sleep(0.1)
    await asyncio.wait_for(wait_for_header_sync(n), 2)

    # https://ropsten.etherscan.io/block/11
    b = await chain.get_canonical_block_by_number(n)
    assert isinstance(b, FrontierBlock)
    assert b.number == 11
    assert encode_hex(b.hash) == (
        '0xda882aeff30f59eda9da2b3ace3023366ab9d4219b5a83cdd589347baae8678e')
    assert len(b.transactions) == 15
    assert isinstance(b.transactions[0], b.transaction_class)

    receipts = await chain.get_receipts(b.hash)
    assert len(receipts) == 15
    assert encode_hex(keccak(rlp.encode(receipts[0]))) == (
        '0xf709ed2c57efc18a1675e8c740f3294c9e2cb36ba7bb3b89d3ab4c8fef9d8860')

    head_info = list(chain._latest_head_info.values())[0]
    head = await chain.get_block_by_hash(head_info.block_hash)
    assert head.number == head_info.block_number

    # In order to answer queries for contract code, geth needs the state trie entry for the block
    # we specify in the query, but because of fast sync we can only assume it has that for recent
    # blocks, so we use the current head to lookup the code for the contract below.
    # https://ropsten.etherscan.io/address/0x95a48dca999c89e4e284930d9b9af973a7481287
    contract_addr = decode_hex('95a48dca999c89e4e284930d9b9af973a7481287')
    contract_code = await chain.get_contract_code(head.hash, keccak(contract_addr))
    assert encode_hex(keccak(contract_code)) == (
        '0x1e0b2ad970b365a217c40bcf3582cbb4fcc1642d7a5dd7a82ae1e278e010123e')

    account = await chain.get_account(head.hash, contract_addr)
    assert account.code_hash == keccak(contract_code)
    assert account.balance == 0
