from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import asyncio
import os
from pathlib import (
    Path,
)
import sys
import time

from ruamel.yaml import (
    YAML,
)
from ssz.tools import (
    to_formatted_dict,
)

from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.state_machines.forks.xiao_long_bao import (
    XiaoLongBaoStateMachine,
)
from eth2.beacon.state_machines.forks.xiao_long_bao.configs import (
    XIAO_LONG_BAO_CONFIG,
)
from eth2.beacon.tools.builder.initializer import (
    create_mock_genesis,
)
from eth2.beacon.tools.misc.ssz_vector import (
    override_vector_lengths,
)
from eth2.beacon.typing import (
    Second,
    Timestamp,
)
from py_ecc import (
    bls,
)
from trinity._utils.shellart import (
    bold_green,
)
from trinity.config import (
    TrinityConfig,
)
from trinity.extensibility import (
    BaseMainProcessPlugin,
)
from trinity.plugins.eth2.constants import (
    VALIDATOR_KEY_DIR,
)

from .constants import (
    GENESIS_FILE,
    KEYS_DIR,
)

override_vector_lengths(XIAO_LONG_BAO_CONFIG)


class Client:
    name: str
    client_dir: Path
    validator_keys_dir: Path

    def __init__(self, name: str, root_dir: Path) -> None:
        self.name = name
        self.client_dir = root_dir / name
        self.validator_keys_dir = self.client_dir / VALIDATOR_KEY_DIR


class NetworkGeneratorPlugin(BaseMainProcessPlugin):
    @property
    def name(self) -> str:
        return "NetworkGenerator"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:

        testnet_generator_parser = subparser.add_parser(
            'testnet',
            help='Generate testnet files',
        )
        testnet_generator_parser.add_argument(
            "--network-dir",
            help="Directory to create all the files into",
            type=Path,
            default=Path("."),
        )
        testnet_generator_parser.add_argument(
            "--num",
            help="Number of validators to generate",
            type=int,
            default=100,
        )
        testnet_generator_parser.add_argument(
            "--genesis-delay",
            help="Seconds before genesis time from now",
            type=int,
            default=60,
        )

        testnet_generator_parser.set_defaults(func=self.run_generate_testnet_dir)

    def run_generate_testnet_dir(self, args: Namespace, trinity_config: TrinityConfig) -> None:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._run_generate_testnet_dir(args))
        loop.close()

    async def _run_generate_testnet_dir(self, args: Namespace) -> None:
        self.logger.info("Generating testnet")
        self.network_dir = args.network_dir
        if len(os.listdir(self.network_dir)) > 0:
            self.logger.error("This directory is not empty, won't create network files here.")
            sys.exit(1)

        self.generate_trinity_root_dirs()
        self.generate_keys(args.num)
        self.generate_genesis_state(args.genesis_delay)

        self.logger.info(bold_green("Network generation completed"))

    def generate_keys(self, num: int) -> None:
        self.logger.info(f"Creating {num} validators' keys")
        self.keys_dir = self.network_dir / KEYS_DIR
        self.keys_dir.mkdir()

        privkeys = tuple(int.from_bytes(
            hash_eth2(str(i).encode('utf-8'))[:4], 'big')
            for i in range(num)
        )
        self.keymap = {bls.privtopub(key): key for key in privkeys}

        num_of_clients = len(self.clients)
        for validator_index, key in enumerate(privkeys):
            file_name = f"v{validator_index:07d}.privkey"
            private_key_path = self.keys_dir / file_name
            with open(private_key_path, "w") as f:
                f.write(str(key))

            # Distribute keys to clients
            client = self.clients[validator_index % num_of_clients]
            with open(client.validator_keys_dir / file_name, "w") as f:
                f.write(str(key))

    def generate_genesis_state(self, genesis_delay: Second) -> None:
        state_machine_class = XiaoLongBaoStateMachine

        # Since create_mock_genesis takes a long time, update the real genesis_time later
        dummy_time = Timestamp(int(time.time()))
        state, _ = create_mock_genesis(
            num_validators=len(self.keymap.keys()),
            config=state_machine_class.config,
            keymap=self.keymap,
            genesis_block_class=state_machine_class.block_class,
            genesis_time=dummy_time,
        )
        self.logger.info(f"Genesis time will be {genesis_delay} seconds from now")
        genesis_time = Timestamp(int(time.time()) + genesis_delay)
        state = state.copy(
            genesis_time=genesis_time,
        )
        yaml = YAML()
        with open(self.network_dir / GENESIS_FILE, "w") as f:
            yaml.dump(to_formatted_dict(state), f)

        # Distribute genesis file to clients
        for client in self.clients:
            with open(client.client_dir / GENESIS_FILE, "w") as f:
                yaml.dump(to_formatted_dict(state), f)

    def generate_trinity_root_dirs(self) -> None:
        self.logger.info("Generating root directories for clients")
        self.clients = tuple(Client(name, self.network_dir) for name in ("alice", "bob"))
        for client in self.clients:
            client.client_dir.mkdir()
            client.validator_keys_dir.mkdir()
