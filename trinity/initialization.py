import os
from typing import Type

from eth.db.backends.base import BaseAtomicDB
from eth.db.chain import BaseChainDB
from eth.exceptions import CanonicalHeadNotFound

from p2p import ecies

from trinity.config import (
    BeaconAppConfig,
    BeaconChainConfig,
    Eth1AppConfig,
    ChainConfig,
    TrinityConfig,
)

from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)
from eth2.beacon.db.chain import BaseBeaconChainDB
from trinity.exceptions import (
    MissingPath,
)
from trinity._utils.filesystem import (
    is_under_path,
)


def is_data_dir_initialized(trinity_config: TrinityConfig) -> bool:
    """
    Return ``True`` if the data directory and all expected sub directories exist,
    otherwise return ``False``
    """

    if not os.path.exists(trinity_config.data_dir):
        return False

    if not os.path.exists(trinity_config.pid_dir):
        return False

    if not os.path.exists(trinity_config.ipc_dir):
        return False

    if not trinity_config.logfile_path.parent.exists():
        return False
    elif not trinity_config.logfile_path.exists():
        return False

    if trinity_config.nodekey_path is None:
        # has an explicitely defined nodekey
        pass
    elif not os.path.exists(trinity_config.nodekey_path):
        return False

    if trinity_config.nodekey is None:
        return False

    return True


def is_database_initialized(chaindb: BaseChainDB) -> bool:
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # empty chain database
        return False
    else:
        return True


def is_beacon_database_initialized(chaindb: BaseBeaconChainDB,
                                   block_class: Type[BaseBeaconBlock]) -> bool:
    try:
        chaindb.get_canonical_head(block_class)
    except CanonicalHeadNotFound:
        # empty chain database
        return False
    else:
        return True


def initialize_data_dir(trinity_config: TrinityConfig) -> None:
    should_create_data_dir = (
        not trinity_config.data_dir.exists() and
        is_under_path(trinity_config.trinity_root_dir, trinity_config.data_dir)
    )
    if should_create_data_dir:
        trinity_config.data_dir.mkdir(parents=True, exist_ok=True)
    elif not trinity_config.data_dir.exists():
        # we don't lazily create the base dir for non-default base directories.
        raise MissingPath(
            f"The base chain directory provided does not exist: `{str(trinity_config.data_dir)}`",
            trinity_config.data_dir,
        )

    # Logfile
    should_create_logdir = (
        not trinity_config.log_dir.exists() and
        (
            # If we're in the default path, always create the log directory
            is_under_path(trinity_config.trinity_root_dir, trinity_config.log_dir) or
            (
                # If we're in a custom path, create the log directory if the data dir is empty
                is_under_path(trinity_config.data_dir, trinity_config.log_dir) and
                not any(trinity_config.data_dir.iterdir())
            )
        )
    )
    if should_create_logdir:
        trinity_config.log_dir.mkdir(parents=True, exist_ok=True)
        trinity_config.logfile_path.touch()
    elif not trinity_config.log_dir.exists():
        # we don't lazily create the base dir for non-default base directories.
        raise MissingPath(
            "The base logging directory provided does not exist: `{0}`".format(
                trinity_config.log_dir,
            ),
            trinity_config.log_dir,
        )

    # Initialize chain, pid and ipc directories
    os.makedirs(trinity_config.pid_dir, exist_ok=True)
    os.makedirs(trinity_config.ipc_dir, exist_ok=True)

    # Nodekey
    if trinity_config.nodekey is None:
        nodekey = ecies.generate_privkey()
        with open(trinity_config.nodekey_path, 'wb') as nodekey_file:
            nodekey_file.write(nodekey.to_bytes())


def initialize_database(chain_config: ChainConfig,
                        chaindb: BaseChainDB,
                        base_db: BaseAtomicDB) -> None:
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        chain_config.initialize_chain(base_db)


def initialize_beacon_database(chain_config: BeaconChainConfig,
                               chaindb: BaseBeaconChainDB,
                               base_db: BaseAtomicDB,
                               block_class: Type[BaseBeaconBlock]) -> None:
    try:
        chaindb.get_canonical_head(block_class)
    except CanonicalHeadNotFound:
        chain_config.initialize_chain(base_db)


def ensure_eth1_dirs(app_config: Eth1AppConfig) -> None:
    if not app_config.database_dir.exists():
        app_config.database_dir.mkdir(parents=True, exist_ok=True)


def ensure_beacon_dirs(app_config: BeaconAppConfig) -> None:
    if not app_config.database_dir.exists():
        app_config.database_dir.mkdir(parents=True, exist_ok=True)
