import os

from evm.chains.ropsten import ROPSTEN_GENESIS_HEADER
from evm.db.backends.level import LevelDB
from evm.db.chain import BaseChainDB
from evm.p2p import ecies
from evm.exceptions import CanonicalHeadNotFound

from trinity.constants import (
    ROPSTEN,
)
from trinity.utils.chains import (
    get_nodekey_path,
    get_data_dir,
    get_chain_dir,
    get_nodekey,
)
from trinity.utils.db import (
    get_chain_db,
)
from trinity.utils.filesystem import (
    ensure_path_exists,
)

from .ropsten import (
    RopstenLightChain,
)


def is_chain_initialized(chain_identifier):
    """
    - chain dir exists
    - chain data-dir exists
    - nodekey exists and is non-empty
    - canonical chain head in db
    """
    chain_dir = get_chain_dir(chain_identifier)
    if not os.path.exists(chain_dir):
        return False

    data_dir = get_data_dir(chain_identifier)
    if not os.path.exists(data_dir):
        return False

    nodekey_path = get_nodekey_path(chain_identifier)
    if not os.path.exists(nodekey_path):
        return False

    with open(nodekey_path, 'rb') as nodekey_file:
        nodekey_raw = nodekey_file.read()
        if not nodekey_raw:
            return False

    chaindb = get_chain_db(chain_identifier)
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        return False

    return True


# TODO: this function shouldn't care about the sync_mode.  We should have some
# sort of `BaseChain` class that we can retrieve which knows how to do the
# header initialization.
def initialize_chain(chain_identifier, sync_mode):
    # Primary chain directory
    chain_dir = get_chain_dir(chain_identifier)
    # TODO: we should only do this for paths *under* the `XDG_TRINITY_HOME`
    # path.  Custom paths should not be lazily created.
    ensure_path_exists(chain_dir)

    # Chain data-dir
    db_path = get_data_dir(chain_identifier)
    ensure_path_exists(db_path)

    # Nodekey
    nodekey_path = get_nodekey_path(chain_identifier)
    if not os.path.exists(nodekey_path):
        nodekey = ecies.generate_privkey()
        with open(nodekey_path, 'wb') as nodekey_file:
            nodekey_file.write(nodekey.to_bytes())

    chain_class = get_chain_protocol_class(chain_identifier, sync_mode)

    # Database Initialization
    chaindb = BaseChainDB(LevelDB(db_path))
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        if chain_identifier == ROPSTEN:
            # We're starting with a fresh DB.
            # TODO: log that we initialized the chain
            chain_class.from_genesis_header(chaindb, ROPSTEN_GENESIS_HEADER)
        else:
            raise NotImplementedError("Not implemented for other chains yet")

    return chain_class


def get_chain_protocol_class(chain_identifier, sync_mode):
    if sync_mode != 'light':
        raise NotImplementedError("Currently, `sync_mode` must be set to 'light'")

    if chain_identifier != 'ropsten':
        raise NotImplementedError("Ropsten is the only chain currently supported.")

    # TODO: need to handle custom nodekeys
    nodekey_path = get_nodekey_path(chain_identifier)
    nodekey = get_nodekey(nodekey_path)

    return RopstenLightChain.configure(
        privkey=nodekey,
    )
