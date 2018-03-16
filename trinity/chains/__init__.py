from multiprocessing.managers import (
    BaseManager,
)
import os
from typing import Type

from evm.chains.mainnet import (
    MAINNET_GENESIS_HEADER,
    MAINNET_NETWORK_ID,
)
from evm.chains.ropsten import (
    ROPSTEN_GENESIS_HEADER,
    ROPSTEN_NETWORK_ID,
)
from evm.db.backends.base import BaseDB
from evm.db.chain import ChainDB
from evm.exceptions import CanonicalHeadNotFound

from p2p import ecies
from p2p.lightchain import LightChain

from trinity.constants import SYNC_LIGHT
from trinity.db.chain import ChainDBProxy
from trinity.db.base import DBProxy
from trinity.utils.chains import (
    ChainConfig,
)
from trinity.utils.xdg import (
    is_under_xdg_trinity_root,
)

from .mainnet import (
    MainnetLightChain,
)
from .ropsten import (
    RopstenLightChain,
)


def is_data_dir_initialized(chain_config: ChainConfig) -> bool:
    """
    - base dir exists
    - chain data-dir exists
    - nodekey exists and is non-empty
    - canonical chain head in db
    """
    if not os.path.exists(chain_config.data_dir):
        return False

    if not os.path.exists(chain_config.database_dir):
        return False

    if chain_config.nodekey_path is None:
        # has an explicitely defined nodekey
        pass
    elif not os.path.exists(chain_config.nodekey_path):
        return False

    if chain_config.nodekey is None:
        return False

    return True


def is_database_initialized(chaindb: ChainDB) -> bool:
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # empty chain database
        return False
    else:
        return True


def initialize_data_dir(chain_config: ChainConfig) -> None:
    if is_under_xdg_trinity_root(chain_config.data_dir):
        os.makedirs(chain_config.data_dir, exist_ok=True)
    elif not os.path.exists(chain_config.data_dir):
        # we don't lazily create the base dir for non-default base directories.
        raise ValueError(
            "The base chain directory provided does not exist: `{0}`".format(
                chain_config.data_dir,
            )
        )

    # Chain data-dir
    os.makedirs(chain_config.database_dir, exist_ok=True)

    # Nodekey
    if chain_config.nodekey is None:
        nodekey = ecies.generate_privkey()
        with open(chain_config.nodekey_path, 'wb') as nodekey_file:
            nodekey_file.write(nodekey.to_bytes())


def initialize_database(chain_config: ChainConfig, chaindb: ChainDB) -> None:
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        if chain_config.network_id == ROPSTEN_NETWORK_ID:
            # We're starting with a fresh DB.
            chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
        elif chain_config.network_id == MAINNET_NETWORK_ID:
            chaindb.persist_header(MAINNET_GENESIS_HEADER)
        else:
            # TODO: add genesis data to ChainConfig and if it's present, use it
            # here to initialize the chain.
            raise NotImplementedError(
                "Only the mainnet and ropsten chains are currently supported"
            )


def get_chain_protocol_class(chain_config: ChainConfig, sync_mode: str) -> Type[LightChain]:
    """
    Retrieve the protocol class for the given chain and sync mode.
    """
    if sync_mode != SYNC_LIGHT:
        raise NotImplementedError("Currently, `sync_mode` must be set to 'light'")

    if chain_config.network_id == MAINNET_NETWORK_ID:
        return MainnetLightChain
    elif chain_config.network_id == ROPSTEN_NETWORK_ID:
        return RopstenLightChain
    else:
        raise NotImplementedError(
            "Only the mainnet and ropsten chains are currently supported"
        )


def serve_chaindb(db: BaseDB, ipc_path: str) -> None:
    chaindb = ChainDB(db)

    class DBManager(BaseManager):
        pass

    # Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
    # https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
    DBManager.register('get_db', callable=lambda: db, proxytype=DBProxy)  # type: ignore
    DBManager.register(  # type: ignore
        'get_chaindb', callable=lambda: chaindb, proxytype=ChainDBProxy)

    manager = DBManager(address=ipc_path)  # type: ignore
    server = manager.get_server()  # type: ignore

    server.serve_forever()  # type: ignore
