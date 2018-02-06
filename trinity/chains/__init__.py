import os

from evm.chains.ropsten import ROPSTEN_GENESIS_HEADER
from evm.p2p import ecies
from evm.exceptions import CanonicalHeadNotFound

from trinity.constants import (
    ROPSTEN,
)
from trinity.utils.db import (
    get_chain_db,
)
from trinity.utils.xdg import (
    is_under_xdg_trinity_root,
)

from .ropsten import (
    RopstenLightChain,
)


def is_chain_initialized(chain_config):
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

    chaindb = get_chain_db(chain_config.database_dir)
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # empty chain database
        return False

    return True


# TODO: this function shouldn't care about the sync_mode.  We should have some
# sort of `BaseChain` class that we can retrieve which knows how to do the
# header initialization.
def initialize_chain(chain_config, sync_mode):
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

    chain_class = get_chain_protocol_class(chain_config, sync_mode)

    # Database Initialization
    chaindb = get_chain_db(chain_config.database_dir)
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        if chain_config.chain_identifier == ROPSTEN:
            # We're starting with a fresh DB.
            # TODO: log that we initialized the chain
            chain_class.from_genesis_header(chaindb, ROPSTEN_GENESIS_HEADER)
        else:
            # TODO: add genesis data to ChainConfig and if it's present, use it
            # here to initialize the chain.
            raise NotImplementedError("Not implemented for other chains yet")

    return chain_class


def get_chain_protocol_class(chain_config, sync_mode):
    """
    Retrieve the protocol class for the given chain and sync mode.
    """
    if sync_mode != 'light':
        raise NotImplementedError("Currently, `sync_mode` must be set to 'light'")

    if chain_config.chain_identifier != 'ropsten':
        raise NotImplementedError("Ropsten is the only chain currently supported.")

    return RopstenLightChain.configure(
        privkey=chain_config.nodekey,
    )
