from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio
from typing import (
    cast,
)

from eth_keys.datatypes import (
    PrivateKey,
)

from eth2.beacon.operations.attestation_pool import AttestationPool
from eth2.beacon.typing import (
    ValidatorIndex,
)

from p2p import ecies
from p2p.constants import (
    DEFAULT_MAX_PEERS,
)

from trinity._utils.shutdown import (
    exit_with_endpoint_and_services,
)
from trinity.db.beacon.manager import (
    create_db_consumer_manager,
)
from trinity.config import BeaconAppConfig
from trinity.endpoint import TrinityEventBusEndpoint
from trinity.extensibility import AsyncioIsolatedPlugin
from trinity.protocol.bcc.peer import BCCPeerPoolEventServer
from trinity.server import BCCServer
from trinity.sync.beacon.chain import BeaconChainSyncer
from trinity.sync.common.chain import (
    SyncBlockImporter,
)

from .slot_ticker import (
    SlotTicker,
)
from .validator import (
    Validator,
)


class BeaconNodePlugin(AsyncioIsolatedPlugin):

    @property
    def name(self) -> str:
        return "Beacon Node"

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--bootstrap_nodes",
            help="enode://node1@0.0.0.0:1234,enode://node2@0.0.0.0:5678",
        )
        arg_parser.add_argument(
            "--preferred_nodes",
            help="enode://node1@0.0.0.0:1234,enode://node2@0.0.0.0:5678",
        )
        arg_parser.add_argument(
            "--beacon-nodekey",
            help="0xabcd",
        )

    def on_ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:
        if self.boot_info.trinity_config.has_app_config(BeaconAppConfig):
            self.start()

    def do_start(self) -> None:
        trinity_config = self.boot_info.trinity_config
        beacon_app_config = trinity_config.get_app_config(BeaconAppConfig)
        db_manager = create_db_consumer_manager(trinity_config.database_ipc_path)
        base_db = db_manager.get_db()  # type: ignore
        chain_db = db_manager.get_chaindb()  # type: ignore
        chain_config = beacon_app_config.get_chain_config()
        attestation_pool = AttestationPool()
        chain = chain_config.beacon_chain_class(
            base_db,
            attestation_pool,
            chain_config.genesis_config
        )

        if self.boot_info.args.beacon_nodekey:
            privkey = PrivateKey(bytes.fromhex(self.boot_info.args.beacon_nodekey))
        else:
            privkey = ecies.generate_privkey()

        server = BCCServer(
            privkey=privkey,
            port=self.boot_info.args.port,
            chain=chain,
            chaindb=chain_db,
            headerdb=None,
            base_db=base_db,
            network_id=trinity_config.network_id,
            max_peers=DEFAULT_MAX_PEERS,
            bootstrap_nodes=None,
            preferred_nodes=None,
            event_bus=self.event_bus,
            token=None,
        )

        event_server = BCCPeerPoolEventServer(
            self.event_bus,
            server.peer_pool,
            server.cancel_token
        )

        syncer = BeaconChainSyncer(
            chain_db=chain_db,
            peer_pool=server.peer_pool,
            block_importer=SyncBlockImporter(chain),
            genesis_config=chain_config.genesis_config,
            token=server.cancel_token,
        )

        state = chain.get_state_by_slot(chain_config.genesis_config.GENESIS_SLOT)
        registry_pubkeys = [v_record.pubkey for v_record in state.validators]

        validator_privkeys = {}
        validator_keymap = chain_config.genesis_data.validator_keymap
        for pubkey in validator_keymap:
            validator_index = cast(ValidatorIndex, registry_pubkeys.index(pubkey))
            validator_privkeys[validator_index] = validator_keymap[pubkey]

        validator = Validator(
            chain=chain,
            peer_pool=server.peer_pool,
            validator_privkeys=validator_privkeys,
            event_bus=self.event_bus,
            token=server.cancel_token,
            get_ready_attestations_fn=server.receive_server.get_ready_attestations,
        )

        slot_ticker = SlotTicker(
            genesis_slot=chain_config.genesis_config.GENESIS_SLOT,
            genesis_time=chain_config.genesis_data.genesis_time,
            seconds_per_slot=chain_config.genesis_config.SECONDS_PER_SLOT,
            event_bus=self.event_bus,
            token=server.cancel_token,
        )

        asyncio.ensure_future(exit_with_endpoint_and_services(self.event_bus, server))
        asyncio.ensure_future(event_server.run())
        asyncio.ensure_future(server.run())
        asyncio.ensure_future(syncer.run())
        asyncio.ensure_future(slot_ticker.run())
        asyncio.ensure_future(validator.run())
