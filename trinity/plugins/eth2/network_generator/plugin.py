from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import os
from pathlib import (
    Path,
)
import sys
import time
from typing import (
    Any,
    Dict,
    Tuple,
)

from ruamel.yaml import (
    YAML,
)
from ssz.tools import (
    to_formatted_dict,
)

from eth2._utils.hash import (
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

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:

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

        testnet_generator_parser.set_defaults(func=cls.run_generate_testnet_dir)

    @classmethod
    def run_generate_testnet_dir(cls, args: Namespace, trinity_config: TrinityConfig) -> None:
        logger = cls.get_logger()
        logger.info("Generating testnet")
        network_dir = args.network_dir
        if len(os.listdir(network_dir)) > 0:
            logger.error("This directory is not empty, won't create network files here.")
            sys.exit(1)

        clients = cls.generate_trinity_root_dirs(network_dir)
        keymap = cls.generate_keys(args.num, network_dir, clients)
        cls.generate_genesis_state(args.genesis_delay, network_dir, keymap, clients)

        logger.info(bold_green("Network generation completed"))

    @classmethod
    def generate_keys(cls,
                      num: int,
                      network_dir: Path,
                      clients: Tuple[Client, ...]) -> Dict[Any, Any]:
        logger = cls.get_logger()
        logger.info(f"Creating {num} validators' keys")
        keys_dir = network_dir / KEYS_DIR
        keys_dir.mkdir()

        privkeys = tuple(int.from_bytes(
            hash_eth2(str(i).encode('utf-8'))[:4], 'big')
            for i in range(num)
        )
        keymap = {bls.privtopub(key): key for key in privkeys}

        num_of_clients = len(clients)
        for validator_index, key in enumerate(privkeys):
            file_name = f"v{validator_index:07d}.privkey"
            private_key_path = keys_dir / file_name
            with open(private_key_path, "w") as f:
                f.write(str(key))

            # Distribute keys to clients
            client = clients[validator_index % num_of_clients]
            with open(client.validator_keys_dir / file_name, "w") as f:
                f.write(str(key))

        return keymap

    @classmethod
    def generate_genesis_state(cls,
                               genesis_delay: Second,
                               network_dir: Path,
                               keymap: Dict[Any, Any],
                               clients: Tuple[Client, ...]) -> None:
        logger = cls.get_logger()
        state_machine_class = XiaoLongBaoStateMachine

        # Since create_mock_genesis takes a long time, update the real genesis_time later
        dummy_time = Timestamp(int(time.time()))
        state, _ = create_mock_genesis(
            num_validators=len(keymap.keys()),
            config=state_machine_class.config,
            keymap=keymap,
            genesis_block_class=state_machine_class.block_class,
            genesis_time=dummy_time,
        )
        logger.info(f"Genesis time will be {genesis_delay} seconds from now")
        genesis_time = Timestamp(int(time.time()) + genesis_delay)
        state = state.copy(
            genesis_time=genesis_time,
        )
        yaml = YAML()
        with open(network_dir / GENESIS_FILE, "w") as f:
            yaml.dump(to_formatted_dict(state), f)

        # Distribute genesis file to clients
        for client in clients:
            with open(client.client_dir / GENESIS_FILE, "w") as f:
                yaml.dump(to_formatted_dict(state), f)

    @classmethod
    def generate_trinity_root_dirs(cls, network_dir: Path) -> Tuple[Client, ...]:
        logger = cls.get_logger()
        logger.info("Generating root directories for clients")
        clients = tuple(Client(name, network_dir) for name in ("alice", "bob"))
        for client in clients:
            client.client_dir.mkdir()
            client.validator_keys_dir.mkdir()
        return clients
