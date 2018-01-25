import os


XDG_CACHE_HOME = os.environ.get(
    'XDG_CACHE_HOME',
    os.path.expandvars(os.path.join('$HOME', '.cache'))
)

XDG_CONFIG_HOME = os.environ.get(
    'XDG_CONFIG_HOME',
    os.path.expandvars(os.path.join('$HOME', '.config')),
)

XDG_DATA_HOME = os.environ.get(
    'XDG_DATA_HOME',
    os.path.expandvars(os.path.join('$HOME', '.local', 'share')),
)


def get_trinity_home():
    """
    Returns the base directory under which trinity will store all data.
    """
    return os.environ.get(
        'TRINITY_HOME',
        os.path.join(XDG_DATA_HOME, 'trinity'),
    )


def get_chain_dir(chain_identifier):
    """
    Returns the base directory path where data for a given chain will be stored.
    """
    return os.environ.get(
        'TRINITY_CHAIN_DIR',
        os.path.join(get_trinity_home(), chain_identifier),
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
