import pathlib
import pytest
import tempfile

from eth_utils import decode_hex

from eth2.configs import Eth2GenesisConfig
from eth2.beacon.fork_choice.higher_slot import higher_slot_scoring
from eth2.beacon.state_machines.forks.serenity.configs import SERENITY_CONFIG
from eth2.beacon.tools.misc.ssz_vector import (
    override_lengths,
)
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.tools.builder.initializer import create_mock_genesis

from trinity.db.beacon.chain import AsyncBeaconChainDB
from trinity.db.manager import DBClient, DBManager
from trinity.rpc.http import handler
from trinity.rpc.main import RPCServer
from trinity.rpc.modules import (
    initialize_beacon_modules,
)


@pytest.fixture
def ipc_path():
    with tempfile.TemporaryDirectory() as dir:
        yield pathlib.Path(dir) / "db_manager.ipc"


async def test_http_server(aiohttp_raw_server, aiohttp_client, event_bus, base_db, ipc_path):
    manager = DBManager(base_db)
    with manager.run(ipc_path):
        # Set chaindb
        override_lengths(SERENITY_CONFIG)
        db = DBClient.connect(ipc_path)
        genesis_config = Eth2GenesisConfig(SERENITY_CONFIG)
        chaindb = AsyncBeaconChainDB(db, genesis_config)

        fork_choice_scoring = higher_slot_scoring
        genesis_state, genesis_block = create_mock_genesis(
            pubkeys=(),
            config=SERENITY_CONFIG,
            keymap=dict(),
            genesis_block_class=BeaconBlock,
            genesis_time=0,
        )

        chaindb.persist_state(genesis_state)
        chaindb.persist_block(genesis_block, genesis_block.__class__, fork_choice_scoring)
        try:
            rpc = RPCServer(initialize_beacon_modules(chaindb, event_bus), chaindb, event_bus)
            raw_server = await aiohttp_raw_server(handler(rpc.execute))
            client = await aiohttp_client(raw_server)

            request_id = 1
            request_data = {
                "jsonrpc": "2.0",
                "method": "beacon_head",
                "params": [],
                "id": request_id,
            }

            response = await client.post('/', json=request_data)
            response_data = await response.json()

            assert response_data['id'] == request_id
            result = response_data['result']
            assert result['slot'] == 0
            assert decode_hex(result['block_root']) == genesis_block.signing_root
            assert decode_hex(result['state_root']) == genesis_state.hash_tree_root
        except KeyboardInterrupt:
            pass
        finally:
            await raw_server.close()
            db.close()
