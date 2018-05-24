import os
from pathlib import PurePath
from typing import (
    Tuple,
    Type,
    Union,
)

from eth_keys import keys
from eth_keys.datatypes import PrivateKey
from evm.chains.mainnet import (
    MAINNET_NETWORK_ID,
)
from evm.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
)
from p2p.kademlia import Node as KademliaNode
from p2p.constants import (
    MAINNET_BOOTNODES,
    ROPSTEN_BOOTNODES,
)

from trinity.constants import (
    SYNC_FULL,
    SYNC_LIGHT,
)
from trinity.nodes.base import (
    Node,
)
from trinity.nodes.mainnet import (
    MainnetLightNode,
)
from trinity.nodes.ropsten import (
    RopstenLightNode,
)
from trinity.utils.chains import (
    construct_chain_config_params,
    get_data_dir_for_network_id,
    get_database_socket_path,
    get_jsonrpc_socket_path,
    get_nodekey_path,
    load_nodekey,
)

DATABASE_DIR_NAME = 'chain'


class ChainConfig:
    _data_dir: PurePath = None
    _nodekey_path: PurePath = None
    _nodekey = None
    _network_id: int = None

    port: int = None
    preferred_nodes: Tuple[KademliaNode, ...] = None

    bootstrap_nodes: Tuple[KademliaNode, ...] = None

    def __init__(self,
                 network_id: int,
                 data_dir: str=None,
                 nodekey_path: str=None,
                 nodekey: PrivateKey=None,
                 sync_mode: str=SYNC_FULL,
                 port: int=30303,
                 preferred_nodes: Tuple[KademliaNode, ...]=None,
                 bootstrap_nodes: Tuple[KademliaNode, ...]=None) -> None:
        self.network_id = network_id
        self.sync_mode = sync_mode
        self.port = port
        self.preferred_nodes = preferred_nodes

        if bootstrap_nodes is None:
            if self.network_id == MAINNET_NETWORK_ID:
                self.bootstrap_nodes = tuple(
                    KademliaNode.from_uri(enode) for enode in MAINNET_BOOTNODES
                )
            elif self.network_id == ROPSTEN_NETWORK_ID:
                self.bootstrap_nodes = tuple(
                    KademliaNode.from_uri(enode) for enode in ROPSTEN_BOOTNODES
                )
        else:
            self.bootstrap_nodes = bootstrap_nodes

        # validation
        if nodekey is not None and nodekey_path is not None:
            raise ValueError("It is invalid to provide both a `nodekey` and a `nodekey_path`")

        # set values
        if data_dir is not None:
            self.data_dir = data_dir
        else:
            self.data_dir = get_data_dir_for_network_id(self.network_id)

        if nodekey_path is not None:
            self.nodekey_path = nodekey_path
        elif nodekey is not None:
            self.nodekey = nodekey

    @property
    def data_dir(self) -> PurePath:
        """
        The data_dir is the base directory that all chain specific information
        for a given chain is stored.  All other chain directories are by
        default relative to this directory.
        """
        return self._data_dir

    @data_dir.setter
    def data_dir(self, value: str) -> None:
        self._data_dir = PurePath(os.path.abspath(value))

    @property
    def database_dir(self) -> str:
        if self.sync_mode == SYNC_FULL:
            return str(self.data_dir / DATABASE_DIR_NAME / "full")
        elif self.sync_mode == SYNC_LIGHT:
            return str(self.data_dir / DATABASE_DIR_NAME / "light")
        else:
            raise ValueError("Unknown sync mode: {}}".format(self.sync_mode))

    @property
    def database_ipc_path(self) -> str:
        return get_database_socket_path(self.data_dir)

    @property
    def jsonrpc_ipc_path(self) -> str:
        return get_jsonrpc_socket_path(self.data_dir)

    @property
    def nodekey_path(self) -> PurePath:
        if self._nodekey_path is None:
            if self._nodekey is not None:
                return None
            else:
                return get_nodekey_path(self.data_dir)
        else:
            return self._nodekey_path

    @nodekey_path.setter
    def nodekey_path(self, value: str) -> None:
        self._nodekey_path = PurePath(os.path.abspath(value))

    @property
    def nodekey(self) -> PrivateKey:
        if self._nodekey is None:
            try:
                return load_nodekey(self.nodekey_path)
            except FileNotFoundError:
                # no file at the nodekey_path so we have a null nodekey
                return None
        else:
            if isinstance(self._nodekey, bytes):
                return keys.PrivateKey(self._nodekey)
            elif isinstance(self._nodekey, PrivateKey):
                return self._nodekey
            return self._nodekey

    @nodekey.setter
    def nodekey(self, value: Union[bytes, PrivateKey]) -> None:
        if isinstance(value, bytes):
            self._nodekey = keys.PrivateKey(value)
        elif isinstance(value, PrivateKey):
            self._nodekey = value
        else:
            raise TypeError(
                "Nodekey must either be a raw byte-string or an eth_keys "
                "`PrivateKey` instance"
            )

    @classmethod
    def from_parser_args(cls, parser_args):
        constructor_kwargs = construct_chain_config_params(parser_args)
        return cls(**constructor_kwargs)

    @property
    def node_class(self) -> Type[Node]:
        if self.sync_mode == SYNC_LIGHT:
            if self.network_id == MAINNET_NETWORK_ID:
                return MainnetLightNode
            elif self.network_id == ROPSTEN_NETWORK_ID:
                return RopstenLightNode
            else:
                raise NotImplementedError(
                    "Only the mainnet and ropsten chains are currently supported"
                )
        elif self.sync_mode == SYNC_FULL:
            raise NotImplementedError(
                "Full sync mode from ChainConfig is not yet supported"
            )
        else:
            raise NotImplementedError(
                "Only full and light sync modes are supported"
            )
