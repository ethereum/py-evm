from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
from pathlib import (
    Path,
)
import sys
import shutil
import time
from typing import Union, TYPE_CHECKING

from eth_utils import (
    to_int,
)
from ruamel.yaml import (
    YAML,
)
from ssz.tools import (
    to_formatted_dict,
)

from eth2.beacon.state_machines.forks.skeleton_lake import MINIMAL_SERENITY_CONFIG
from eth2.beacon.tools.misc.ssz_vector import (
    override_lengths,
)
from trinity.config import (
    TrinityConfig,
    BeaconAppConfig,
)
from trinity.extensibility import (
    BaseMainProcessComponent,
)
import ssz

from eth2.beacon.types.states import BeaconState

from trinity.components.eth2.constants import (
    GENESIS_FILE,
    VALIDATOR_KEY_DIR,
)

from trinity.components.builtin.network_db.component import TrackingBackend

if TYPE_CHECKING:
    from typing import Any, IO  # noqa: F401


class InteropComponent(BaseMainProcessComponent):
    @property
    def name(self) -> str:
        return "Interop"

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:

        interop_parser = subparser.add_parser(
            'interop',
            help='Run with a hard-coded configuration',
        )

        time_group = interop_parser.add_mutually_exclusive_group(
            required=False,
        )
        time_group.add_argument(
            '--start-time',
            help="Unix timestamp to use as genesis start time",
            type=int,
        )
        time_group.add_argument(
            '--start-delay',
            help="How many seconds until the genesis is active",
            type=int,
        )

        validator_group = interop_parser.add_mutually_exclusive_group(
            required=False,
        )

        validator_group.add_argument(
            '--validators',
            help="Which validators should run",
            type=str,
        )

        validator_group.add_argument(
            '--validators-from-yaml-key-file',
            help="Which validators should run, inferred by provided key pairs",
            type=str,
        )

        interop_parser.add_argument(
            '--genesis-state-ssz-path',
            help="Path to a SSZ-encoded genesis state",
            type=str,
        )

        interop_parser.add_argument(
            '--wipedb',
            help="Blows away the chaindb so we can start afresh",
            action='store_true',
        )

        interop_parser.set_defaults(munge_func=cls.munge_all_args)

    @classmethod
    def munge_all_args(cls, args: Namespace, trinity_config: TrinityConfig) -> None:
        logger = cls.get_logger()
        logger.info("Configuring testnet")

        override_lengths(MINIMAL_SERENITY_CONFIG)

        if args.wipedb:
            beacon_config = trinity_config.get_app_config(BeaconAppConfig)
            logger.info(f'Blowing away the database: {beacon_config.database_dir}')
            try:
                shutil.rmtree(beacon_config.database_dir)
            except FileNotFoundError:
                # there's nothing to wipe, that's fine!
                pass
            else:
                beacon_config.database_dir.mkdir()

        genesis_path = args.genesis_state_ssz_path or Path('resources/genesis.ssz')
        logger.info(f"Using genesis from {genesis_path}")

        # read the genesis!
        try:
            with open(genesis_path, 'rb') as f:  # type: IO[Any]
                encoded = f.read()
            state = ssz.decode(encoded, sedes=BeaconState)
        except FileNotFoundError:
            import os
            logger.critical(
                "Required: the genesis state at %s/genesis.ssz,"
                " or the path to this state with command line"
                " argument `--genesis-state-ssz-path $PATH`",
                os.getcwd(),
            )
            sys.exit(1)

        now = int(time.time())
        if args.start_time:
            if args.start_time <= now:
                logger.warning(f"--start-time must be a time in the future. Current time is {now}")

            delta = args.start_time - now
            logger.info("Time will begin %d seconds from now", delta)

            # adapt the state, then print the new root!
            state = state.copy(
                genesis_time=args.start_time
            )
        elif args.start_delay:
            if args.start_delay < 0:
                logger.info(f"--start-time must be positive")
                sys.exit(1)

            start_time = now + args.start_delay
            logger.info("Genesis time is %d", start_time)

            state = state.copy(
                genesis_time=start_time
            )
        else:
            logger.info("Using genesis_time from genesis state to determine start time")

        logger.info(f"Genesis hash tree root: {state.hash_tree_root.hex()}")

        logger.info(f"Configuring {trinity_config.trinity_root_dir}")

        # Save the genesis state to the data dir!
        yaml = YAML(typ='unsafe')
        with open(trinity_config.trinity_root_dir / GENESIS_FILE, 'w') as f:
            yaml.dump(to_formatted_dict(state), f)

        # Save the validator keys to the data dir
        keys_dir = trinity_config.trinity_root_dir / VALIDATOR_KEY_DIR
        try:
            shutil.rmtree(keys_dir)
        except FileNotFoundError:
            pass
        keys_dir.mkdir()

        def parse_key(maybe_hexstr: str) -> Union[int, str]:
            try:
                return to_int(hexstr=maybe_hexstr)
            except TypeError:
                return maybe_hexstr

        validators = args.validators
        if (args.validators or args.validators_from_yaml_key_file):
            if not validators:
                validators_keys_file = args.validators_from_yaml_key_file
                yaml = YAML(typ="unsafe")
                keys = yaml.load(Path(validators_keys_file))
                for (i, key) in enumerate(keys):
                    file_name = f"v_{i}.privkey"
                    key_path = keys_dir / file_name
                    with open(key_path, "w") as f:
                        f.write(str(parse_key(key['privkey'])))
            else:
                validators = [int(token) for token in validators.split(',')]
                for validator in validators:
                    if validator < 0 or validator > 15:
                        logger.error(f"{validator} is not a valid validator")
                        sys.exit(1)
                logger.info(f"Validating: {validators}")
                yaml = YAML(typ="unsafe")
                keys = yaml.load(
                    Path(
                        'eth2/beacon/scripts/quickstart_state/keygen_16_validators.yaml'
                    )
                )

                for validator_index in validators:
                    key = keys[validator_index]
                    file_name = f"v{validator_index:07d}.privkey"
                    key_path = keys_dir / file_name
                    with open(key_path, "w") as f:
                        f.write(str(parse_key(key['privkey'])))
        else:
            logger.info("not running any validators")

        # disable some components which shouldn't be running
        args.disable_discovery = True
        args.disable_upnp = True
        args.network_tracking_backend = TrackingBackend.DO_NOT_TRACK
