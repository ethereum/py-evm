import argparse
from contextlib import contextmanager
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Tuple,
    Type,
    Union,
)

from eth_keys import keys
from eth_keys.datatypes import PrivateKey
from eth.chains.mainnet import (
    MAINNET_NETWORK_ID,
)
from eth.chains.ropsten import (
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
from trinity.protocol.common.constants import DEFAULT_PREFERRED_NODES
from trinity.utils.chains import (
    construct_chain_config_params,
    get_data_dir_for_network_id,
    get_database_socket_path,
    get_jsonrpc_socket_path,
    get_logfile_path,
    get_nodekey_path,
    load_nodekey,
)
from trinity.utils.filesystem import (
    PidFile,
)
from trinity.utils.xdg import (
    get_xdg_trinity_root,
)


if TYPE_CHECKING:
    # avoid circular import
    from trinity.nodes.base import Node  # noqa: F401

DATABASE_DIR_NAME = 'chain'


class ChainConfig:
    _trinity_root_dir: Path = None
    _data_dir: Path = None
    _nodekey_path: Path = None
    _logfile_path: Path = None
    _nodekey = None
    _network_id: int = None

    port: int = None
    preferred_nodes: Tuple[KademliaNode, ...] = None

    bootstrap_nodes: Tuple[KademliaNode, ...] = None

    def __init__(self,
                 network_id: int,
                 max_peers: int=25,
                 trinity_root_dir: str=None,
                 data_dir: str=None,
                 nodekey_path: str=None,
                 logfile_path: str=None,
                 nodekey: PrivateKey=None,
                 sync_mode: str=SYNC_FULL,
                 port: int=30303,
                 use_discv5: bool = False,
                 preferred_nodes: Tuple[KademliaNode, ...]=None,
                 bootstrap_nodes: Tuple[KademliaNode, ...]=None) -> None:
        self.network_id = network_id
        self.max_peers = max_peers
        self.sync_mode = sync_mode
        self.port = port
        self.use_discv5 = use_discv5

        if trinity_root_dir is not None:
            self.trinity_root_dir = trinity_root_dir

        if not preferred_nodes and network_id in DEFAULT_PREFERRED_NODES:
            self.preferred_nodes = DEFAULT_PREFERRED_NODES[self.network_id]
        else:
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

        if data_dir is not None:
            self.data_dir = data_dir

        if nodekey is not None and nodekey_path is not None:
            raise ValueError("It is invalid to provide both a `nodekey` and a `nodekey_path`")
        elif nodekey_path is not None:
            self.nodekey_path = nodekey_path
        elif nodekey is not None:
            self.nodekey = nodekey

        if logfile_path is not None:
            self.logfile_path = logfile_path

    @property
    def logfile_path(self) -> Path:
        """
        Return the path to the log file.
        """
        if self._logfile_path is not None:
            return self._logfile_path
        else:
            return get_logfile_path(self.data_dir)

    @logfile_path.setter
    def logfile_path(self, value: Path) -> None:
        self._logfile_path = value

    @property
    def logdir_path(self) -> Path:
        """
        Return the path of the directory where all log files are stored.
        """
        return self.logfile_path.parent

    @property
    def trinity_root_dir(self) -> Path:
        """
        The trinity_root_dir is the base directory that all trinity data is
        stored under.

        The default ``data_dir`` path will be resolved relative to this
        directory.
        """
        if self._trinity_root_dir is not None:
            return self._trinity_root_dir
        else:
            return get_xdg_trinity_root()

    @trinity_root_dir.setter
    def trinity_root_dir(self, value: str) -> None:
        self._trinity_root_dir = Path(value).resolve()

    @property
    def data_dir(self) -> Path:
        """
        The data_dir is the base directory that all chain specific information
        for a given chain is stored.

        All defaults for chain directories are resolved relative to this
        directory.
        """
        if self._data_dir is not None:
            return self._data_dir
        else:
            return get_data_dir_for_network_id(self.network_id, self.trinity_root_dir)

    @data_dir.setter
    def data_dir(self, value: str) -> None:
        self._data_dir = Path(value).resolve()

    @property
    def database_dir(self) -> Path:
        """
        Path where the chain database will be stored.

        This is resolved relative to the ``data_dir``
        """
        if self.sync_mode == SYNC_FULL:
            return self.data_dir / DATABASE_DIR_NAME / "full"
        elif self.sync_mode == SYNC_LIGHT:
            return self.data_dir / DATABASE_DIR_NAME / "light"
        else:
            raise ValueError("Unknown sync mode: {}".format(self.sync_mode))

    @property
    def database_ipc_path(self) -> Path:
        """
        Path for the database IPC socket connection.
        """
        return get_database_socket_path(self.data_dir)

    @property
    def jsonrpc_ipc_path(self) -> Path:
        """
        Path for the JSON-RPC server IPC socket.
        """
        return get_jsonrpc_socket_path(self.data_dir)

    @property
    def nodekey_path(self) -> Path:
        """
        Path where the nodekey is stored
        """
        if self._nodekey_path is None:
            if self._nodekey is not None:
                return None
            else:
                return get_nodekey_path(self.data_dir)
        else:
            return self._nodekey_path

    @nodekey_path.setter
    def nodekey_path(self, value: str) -> None:
        self._nodekey_path = Path(value).resolve()

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
    def from_parser_args(cls, parser_args: argparse.Namespace) -> 'ChainConfig':
        """
        Helper function for initializing from the namespace object produced by
        an ``argparse.ArgumentParser``
        """
        constructor_kwargs = construct_chain_config_params(parser_args)
        return cls(**constructor_kwargs)

    @property
    def node_class(self) -> Type['Node']:
        """
        The ``Node`` class that trinity will use.
        """
        from trinity.nodes.mainnet import (
            MainnetFullNode,
            MainnetLightNode,
        )
        from trinity.nodes.ropsten import (
            RopstenFullNode,
            RopstenLightNode,
        )
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
            if self.network_id == MAINNET_NETWORK_ID:
                return MainnetFullNode
            elif self.network_id == ROPSTEN_NETWORK_ID:
                return RopstenFullNode
            else:
                raise NotImplementedError(
                    "Only the mainnet and ropsten chains are currently supported"
                )
        else:
            raise NotImplementedError(
                "Only full and light sync modes are supported"
            )

    @contextmanager
    def process_id_file(self, process_name: str):  # type: ignore
        with PidFile(process_name, self.data_dir):
            yield
