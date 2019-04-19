from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import asyncio
import json
import os
from pathlib import (
    Path,
)
import shutil
import sys
from typing import (
    NamedTuple,
)
import time
from eth_utils import (
    encode_hex,
)
from py_ecc import (
    bls,
)

from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.typing import (
    Second,
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
    DEPOSITS_DIR,
    KEYS_DIR,
)

from eth2.beacon.types.deposits import (
    Deposit,
)
from eth2.beacon.types.forks import (
    Fork,
)
from eth2.beacon.tools.builder.validator import (
    create_deposit_data,
)
from eth2.beacon.state_machines.forks.xiao_long_bao import (
    XiaoLongBaoStateMachine,
)


class Validator:
    index: int
    private_key: int
    public_key: str
    deposit_filename: str
    private_key_filename: str

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


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
            default=400,
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

    async def _run_generate_testnet_dir(self, args: Namespace)-> None:
        self.logger.info("Generating testnet")
        self.network_dir = args.network_dir
        if len(os.listdir(self.network_dir)) > 0:
            self.logger.error("This directory is not empty, won't create network files here.")
            sys.exit(1)

        self.generate_keys(args.num)
        self.generate_genesis_state(args.genesis_delay)
        self.generate_trinity_root_dirs()

        self.logger.info(bold_green("Network generation completed"))

    def generate_keys(self, num: int) -> None:
        self.logger.info("Creating %s validators' keys and deposits" % (num))
        self.keys_dir = self.network_dir / KEYS_DIR
        self.keys_dir.mkdir()
        self.deposits_dir = self.network_dir / DEPOSITS_DIR
        self.deposits_dir.mkdir()

        privkeys = tuple(int.from_bytes(
            hash_eth2(str(i).encode('utf-8'))[:4], 'big')
            for i in range(num)
        )
        self.validators = tuple(
            Validator(
                index=index,
                private_key=key,
                public_key=bls.privtopub(key),
                deposit_filename=f"v{index:07d}.deposit.json",
                private_key_filename=f"v{index:07d}.privkey",
            )
            for index, key in enumerate(privkeys)
        )
        config = XiaoLongBaoStateMachine.config

        for validator in self.validators:
            if validator.index % 50 == 0:
                self.logger.info("%s\tvalidators processed" % (validator.index))
            deposit_path = self.deposits_dir / validator.deposit_filename
            private_key_path = self.keys_dir / validator.private_key_filename

            fork = Fork(
                previous_version=config.GENESIS_FORK_VERSION.to_bytes(4, 'little'),
                current_version=config.GENESIS_FORK_VERSION.to_bytes(4, 'little'),
                epoch=config.GENESIS_EPOCH,
            )
            deposit = Deposit(
                proof=[b'\x00' * 32] * config.DEPOSIT_CONTRACT_TREE_DEPTH,
                index=validator.index,
                deposit_data=create_deposit_data(
                    config=config,
                    pubkey=validator.public_key,
                    privkey=validator.private_key,
                    withdrawal_credentials=b'\x56' * 32,
                    fork=fork,
                    deposit_timestamp=int(time.time()),
                )
            )
            with open(deposit_path, "w") as f:
                json.dump(deposit.to_formatted_dict(), f, indent=4)
            with open(private_key_path, "w") as f:
                f.write(str(validator.private_key))

    def generate_genesis_state(self, genesis_delay: Second) -> None:
        pass

    def generate_trinity_root_dirs(self) -> None:
        self.logger.info("Generating root directories for clients")
        clients = ("alice", "bob")

        for index, client in enumerate(clients):
            client_path = self.network_dir / client
            client_path.mkdir()
            validator_keys_dir = client_path / VALIDATOR_KEY_DIR
            validator_keys_dir.mkdir()
            for validator_index, validator in enumerate(self.validators):
                if validator_index % len(client) == index:
                    from_path = self.keys_dir / validator.private_key_filename
                    to_path = validator_keys_dir / validator.private_key_filename
                    shutil.copyfile(from_path, to_path)
