import argparse
import os
import json
from pathlib import Path
from typing import (
    Dict,
    Iterable,
    Tuple,
    Type,
    Union,
)

from eth_utils import (
    decode_hex,
    to_dict,
    ValidationError
)

from eth import constants
from eth_keys import keys
from eth_keys.datatypes import PrivateKey

from eth.chains.mainnet import (
    MAINNET_NETWORK_ID,
)
from eth.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
)

from eth.vm.base import (
    BaseVM
)

from eth.vm.forks import (
    TangerineWhistleVM,
    HomesteadVM,
    SpuriousDragonVM,
    ByzantiumVM,
    ConstantinopleVM,
)

from p2p.constants import DEFAULT_MAX_PEERS

from trinity.constants import SYNC_LIGHT

from eth.rlp.headers import BlockHeader


DEFAULT_DATA_DIRS = {
    ROPSTEN_NETWORK_ID: 'ropsten',
    MAINNET_NETWORK_ID: 'mainnet',
}


def get_genesis_vm_configuration(genesis: Dict[str, str]) -> Tuple[Tuple[int, Type[BaseVM]], ...]:
    """
    Returns a vm configuration which is a tuple of block numbers associated to a fork
    based on the genesis config provided.
    """
    custom_chain_config = genesis['config']
    vm_configuration = []
    if 'homesteadBlock' in custom_chain_config.keys():
        vm_configuration.append((custom_chain_config["homesteadBlock"], HomesteadVM))
    if 'eip150Block' in custom_chain_config.keys():
        vm_configuration.append((custom_chain_config["eip150Block"], TangerineWhistleVM))
    if 'eip158Block' in custom_chain_config.keys():
        vm_configuration.append((custom_chain_config['eip158Block'], SpuriousDragonVM))
    if 'byzantiumBlock' in custom_chain_config.keys():
        vm_configuration.append((custom_chain_config['byzantiumBlock'], ByzantiumVM))
    if 'constantinopleBlock' in custom_chain_config.keys():
        vm_configuration.append((custom_chain_config['constantinopleBlock'], ConstantinopleVM))

    return tuple(vm_configuration)


def get_genesis_header(genesis: Dict[str, str]) -> Tuple[BlockHeader, int]:
    """
    Returns the genesis config wrapped as a BlockHeader along with the network_id
    of the chain.
    """
    return BlockHeader(
        difficulty=int(genesis['difficulty'], 0),
        extra_data=decode_hex(genesis['extraData']),
        gas_limit=int(genesis['gasLimit'], 0),
        gas_used=0,
        bloom=0,
        mix_hash=constants.ZERO_HASH32,
        nonce=constants.GENESIS_NONCE,
        block_number=0,
        parent_hash=constants.ZERO_HASH32,
        receipt_root=constants.BLANK_ROOT_HASH,
        uncles_hash=constants.EMPTY_UNCLE_HASH,
        state_root=decode_hex("0xd7f8974fb5ac78d9ac099b9ad5018bedc2ce0a72dad1827a1709da30580f0544"),
        timestamp=0,
        transaction_root=constants.BLANK_ROOT_HASH,
    ), genesis['config']['chainId']


def validate_eip1085_genesis_config(genesis: Dict[str, str]) -> None:
    """
    Checks that all valid genesis config parameters are present from the decoded
    genesis JSON config specified. If any of the required parameters are missing
    the function will raise a ValidationError.
    """
    if 'difficulty' not in genesis.keys():
        raise ValidationError("genesis config missing required 'difficulty'")
    if 'gasLimit' not in genesis.keys():
        raise ValidationError("genesis config missing required 'gasLimit'")
    if 'nonce' not in genesis.keys():
        raise ValidationError("genesis config missing required 'nonce'")
    if 'extraData' not in genesis.keys():
        raise ValidationError("genesis config missing required 'extraData'")
    if 'config' not in genesis.keys():
        raise ValidationError("genesis config missing required 'config'")
    if 'chainId' not in genesis['config'].keys():
        raise ValidationError("genesis config missing required 'chainId'")


def get_eip1085_genesis_config(genesis_path: Path) -> Dict[str, str]:
    """
    Will attempt to decode, validate and return a BlockHeader based on the filepath
    given for the genesis config. The genesis config should conform to genesis
    portion of https://github.com/ethereum/EIPs/issues/1085.
    """
    if not os.path.exists(genesis_path):
        raise FileNotFoundError(
            "The base chain genesis configuration file does not exist: `{0}`".format(
                genesis_path,
            ),
        )

    with open(genesis_path, 'r') as genesis_config:
        genesis = json.load(genesis_config)

    validate_eip1085_genesis_config(genesis)

    return genesis


#
# Filesystem path utils
#
def get_local_data_dir(chain_name: str, trinity_root_dir: Path) -> Path:
    """
    Returns the base directory path where data for a given chain will be stored.
    """
    try:
        return Path(os.environ['TRINITY_DATA_DIR'])
    except KeyError:
        return trinity_root_dir / chain_name


def get_data_dir_for_network_id(network_id: int, trinity_root_dir: Path) -> Path:
    """
    Returns the data directory for the chain associated with the given network
    id.  If the network id is unknown, raises a KeyError.
    """
    try:
        return get_local_data_dir(DEFAULT_DATA_DIRS[network_id], trinity_root_dir)
    except KeyError:
        raise KeyError("Unknown network id: `{0}`".format(network_id))


LOG_DIRNAME = 'logs'
LOG_FILENAME = 'trinity.log'


def get_logfile_path(data_dir: Path) -> Path:
    """
    Return the path to the log file.
    """
    return data_dir / LOG_DIRNAME / LOG_FILENAME


NODEKEY_FILENAME = 'nodekey'


def get_nodekey_path(data_dir: Path) -> Path:
    """
    Returns the path to the private key used for devp2p connections.
    """
    return Path(os.environ.get(
        'TRINITY_NODEKEY',
        str(data_dir / NODEKEY_FILENAME),
    ))


DATABASE_SOCKET_FILENAME = 'db.ipc'


def get_database_socket_path(data_dir: Path) -> Path:
    """
    Returns the path to the private key used for devp2p connections.

    We're still returning 'str' here on ipc-related path because an issue with
    multi-processing not being able to interpret 'Path' objects correctly.
    """
    return Path(os.environ.get(
        'TRINITY_DATABASE_IPC',
        data_dir / DATABASE_SOCKET_FILENAME,
    ))


JSONRPC_SOCKET_FILENAME = 'jsonrpc.ipc'


def get_jsonrpc_socket_path(data_dir: Path) -> Path:
    """
    Returns the path to the ipc socket for the JSON-RPC server.

    We're still returning 'str' here on ipc-related path because an issue with
    multi-processing not being able to interpret 'Path' objects correctly.
    """
    return Path(os.environ.get(
        'TRINITY_JSONRPC_IPC',
        data_dir / JSONRPC_SOCKET_FILENAME,
    ))


#
# Nodekey loading
#
def load_nodekey(nodekey_path: Path) -> PrivateKey:
    with nodekey_path.open('rb') as nodekey_file:
        nodekey_raw = nodekey_file.read()
    nodekey = keys.PrivateKey(nodekey_raw)
    return nodekey


@to_dict
def construct_chain_config_params(
        args: argparse.Namespace) -> Iterable[Tuple[str, Union[int, str, Tuple[str, ...]]]]:
    """
    Helper function for constructing the kwargs to initialize a ChainConfig object.
    """
    yield 'network_id', args.network_id
    yield 'use_discv5', args.discv5

    if args.trinity_root_dir is not None:
        yield 'trinity_root_dir', args.trinity_root_dir

    if args.genesis is not None:
        if args.data_dir is None:
            raise ValueError("Must provide both genesis and data-dir")
        yield 'genesis', args.genesis
    if args.data_dir is not None:
        yield 'data_dir', args.data_dir

    if args.nodekey_path and args.nodekey:
        raise ValueError("Cannot provide both nodekey_path and nodekey")
    elif args.nodekey_path is not None:
        yield 'nodekey_path', args.nodekey_path
    elif args.nodekey is not None:
        yield 'nodekey', decode_hex(args.nodekey)

    if args.sync_mode is not None:
        yield 'sync_mode', args.sync_mode

    if args.max_peers is not None:
        yield 'max_peers', args.max_peers
    else:
        yield 'max_peers', _default_max_peers(args.sync_mode)

    if args.port is not None:
        yield 'port', args.port

    if args.preferred_nodes is None:
        yield 'preferred_nodes', tuple()
    else:
        yield 'preferred_nodes', tuple(args.preferred_nodes)


def _default_max_peers(sync_mode: str) -> int:
    if sync_mode == SYNC_LIGHT:
        return DEFAULT_MAX_PEERS // 2
    else:
        return DEFAULT_MAX_PEERS
