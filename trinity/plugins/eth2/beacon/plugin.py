from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio
from typing import (
    Tuple,
    cast,
)

from lahja import EndpointAPI


from libp2p.crypto.keys import KeyPair
from libp2p.crypto.secp256k1 import create_new_key_pair, Secp256k1PrivateKey

from eth2.beacon.operations.attestation_pool import AttestationPool
from eth2.beacon.types.attestations import (
    Attestation,
)
from eth2.beacon.typing import (
    ValidatorIndex,
)

from trinity._utils.shutdown import (
    exit_with_services,
)
from trinity.config import BeaconAppConfig
from trinity.db.manager import DBClient
from trinity.extensibility import AsyncioIsolatedPlugin
from trinity.protocol.bcc_libp2p.node import Node

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
            help="/ip4/127.0.0.1/tcp/1234/p2p/node1_peer_id,/ip4/127.0.0.1/tcp/5678/p2p/node2_peer_id",  # noqa: E501
        )
        arg_parser.add_argument(
            "--preferred_nodes",
            help="/ip4/127.0.0.1/tcp/1234/p2p/node1_peer_id,/ip4/127.0.0.1/tcp/5678/p2p/node2_peer_id",  # noqa: E501
        )
        arg_parser.add_argument(
            "--beacon-nodekey",
            help="0xabcd",
        )

    def on_ready(self, manager_eventbus: EndpointAPI) -> None:
        if self.boot_info.trinity_config.has_app_config(BeaconAppConfig):
            self.start()

    def do_start(self) -> None:
        trinity_config = self.boot_info.trinity_config
        beacon_app_config = trinity_config.get_app_config(BeaconAppConfig)
        base_db = DBClient.connect(trinity_config.database_ipc_path)
        chain_config = beacon_app_config.get_chain_config()
        attestation_pool = AttestationPool()
        chain = chain_config.beacon_chain_class(
            base_db,
            attestation_pool,
            chain_config.genesis_config
        )

        key_pair: KeyPair
        if self.boot_info.args.beacon_nodekey:
            privkey = Secp256k1PrivateKey(bytes.fromhex(self.boot_info.args.beacon_nodekey))
            key_pair = KeyPair(private_key=privkey, public_key=privkey.get_public_key())
        else:
            key_pair = create_new_key_pair()

        # TODO: Handle `bootstrap_nodes`.
        libp2p_node = Node(
            key_pair=key_pair,
            listen_ip="127.0.0.1",  # FIXME: Should be configurable
            listen_port=self.boot_info.args.port,
            preferred_nodes=trinity_config.preferred_nodes,
            chain=chain,
        )

        state = chain.get_state_by_slot(chain_config.genesis_config.GENESIS_SLOT)
        registry_pubkeys = [v_record.pubkey for v_record in state.validators]

        validator_privkeys = {}
        validator_keymap = chain_config.genesis_data.validator_keymap
        for pubkey in validator_keymap:
            validator_index = cast(ValidatorIndex, registry_pubkeys.index(pubkey))
            validator_privkeys[validator_index] = validator_keymap[pubkey]

        def fake_get_ready_attestations_fn() -> Tuple[Attestation, ...]:
            return tuple()

        validator = Validator(
            chain=chain,
            p2p_node=libp2p_node,
            validator_privkeys=validator_privkeys,
            event_bus=self.event_bus,
            token=libp2p_node.cancel_token,
            get_ready_attestations_fn=fake_get_ready_attestations_fn,  # FIXME: BCCReceiveServer.get_ready_attestations  # noqa: E501
        )

        slot_ticker = SlotTicker(
            genesis_slot=chain_config.genesis_config.GENESIS_SLOT,
            genesis_time=chain_config.genesis_data.genesis_time,
            seconds_per_slot=chain_config.genesis_config.SECONDS_PER_SLOT,
            event_bus=self.event_bus,
            token=libp2p_node.cancel_token,
        )

        asyncio.ensure_future(exit_with_services(
            self._event_bus_service,
            libp2p_node,
            slot_ticker,
            validator,
        ))
        asyncio.ensure_future(libp2p_node.run())
        asyncio.ensure_future(slot_ticker.run())
        asyncio.ensure_future(validator.run())
