import os

from eth_keys import keys

from .xdg import (
    get_xdg_trinity_home,
)


def get_chain_dir(chain_identifier):
    """
    Returns the base directory path where data for a given chain will be stored.
    """
    return os.environ.get(
        'TRINITY_CHAIN_DIR',
        os.path.join(get_xdg_trinity_home(), chain_identifier),
    )


DATA_DIR_NAME = 'chain'


def get_data_dir(chain_identifier):
    """
    Returns the directory path where chain data will be stored.
    """
    return os.environ.get(
        'TRINITY_DATA_DIR',
        os.path.join(get_chain_dir(chain_identifier), DATA_DIR_NAME),
    )


NODEKEY_FILENAME = 'nodekey'


def get_nodekey_path(chain_identifier):
    """
    Returns the path to the private key used for devp2p connections.
    """
    return os.environ.get(
        'TRINITY_NODEKEY',
        os.path.join(get_chain_dir(chain_identifier), NODEKEY_FILENAME),
    )


def get_nodekey(nodekey_path):
    with open(nodekey_path, 'rb') as nodekey_file:
        nodekey_raw = nodekey_file.read()
    nodekey = keys.PrivateKey(nodekey_raw)
    return nodekey
