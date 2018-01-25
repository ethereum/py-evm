import os

from evm.p2p import ecies
from evm.exceptions import CanonicalHeadNotFound

from trinity.utils.chains import (
    get_nodekey_path,
    get_data_dir,
    get_chain_dir,
)
from trinity.utils.db import (
    get_chain_db,
)

from .ropsten import (
    BaseRopstenLightChain,
)


NAMED_CHAINS = {
    'ropsten': BaseRopstenLightChain,
}


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


def get_chain(chain_identifier):
    chaindb = BaseChainDB(LevelDB(db_path))
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # We're starting with a fresh DB.
        chain = DemoLightChain.from_genesis_header(chaindb, ROPSTEN_GENESIS_HEADER)
    else:
        # We're reusing an existing db.
        chain = DemoLightChain(chaindb)
