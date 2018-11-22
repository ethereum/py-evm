import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from typing import (
    Any,
    cast,
    Dict,
    TYPE_CHECKING,
    Tuple,
    Type,
    Union,
)

from eth_typing import (
    Address,
)

from eth_keys import keys
from eth_keys.datatypes import PrivateKey

from eth.db.backends.base import BaseAtomicDB
from eth.typing import VMConfiguration

from p2p.kademlia import Node as KademliaNode
from p2p.constants import (
    MAINNET_BOOTNODES,
    ROPSTEN_BOOTNODES,
)

from trinity.constants import (
    ASSETS_DIR,
    DEFAULT_PREFERRED_NODES,
    MAINNET_NETWORK_ID,
    ROPSTEN_NETWORK_ID,
    SYNC_FULL,
    SYNC_LIGHT,
)
from trinity.utils.chains import (
    construct_trinity_config_params,
    get_data_dir_for_network_id,
    get_database_socket_path,
    get_jsonrpc_socket_path,
    get_logfile_path,
    get_nodekey_path,
    load_nodekey,
)
from trinity.utils.eip1085 import (
    Account,
    GenesisData,
    GenesisParams,
    extract_genesis_data,
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
    from trinity.chains.full import FullChain  # noqa: F401
    from trinity.chains.light import LightDispatchChain  # noqa: F401

DATABASE_DIR_NAME = 'chain'


MAINNET_EIP1085_PATH = ASSETS_DIR / 'eip1085' / 'mainnet.json'
ROPSTEN_EIP1085_PATH = ASSETS_DIR / 'eip1085' / 'ropsten.json'


PRECONFIGURED_NETWORKS = {MAINNET_NETWORK_ID, ROPSTEN_NETWORK_ID}


def _load_preconfigured_genesis_config(network_id: int) -> Dict[str, Any]:
    if network_id == MAINNET_NETWORK_ID:
        with MAINNET_EIP1085_PATH.open('r') as mainnet_genesis_file:
            return json.load(mainnet_genesis_file)
    elif network_id == ROPSTEN_NETWORK_ID:
        with ROPSTEN_EIP1085_PATH.open('r') as ropsten_genesis_file:
            return json.load(ropsten_genesis_file)
    else:
        raise TypeError(f"Unknown or unsupported `network_id`: {network_id}")


def _get_preconfigured_chain_name(network_id: int) -> str:
    if network_id == MAINNET_NETWORK_ID:
        return 'MainnetChain'
    elif network_id == ROPSTEN_NETWORK_ID:
        return 'RopstenChain'
    else:
        raise TypeError(f"Unknown or unsupported `network_id`: {network_id}")


class ChainConfig:
    def __init__(self,
                 genesis_data: GenesisData,
                 chain_name: str=None) -> None:

        self.genesis_data = genesis_data
        self._chain_name = chain_name

    @property
    def chain_name(self) -> str:
        if self._chain_name is None:
            return "CustomChain"
        else:
            return self._chain_name

    @property
    def full_chain_class(self) -> Type['FullChain']:
        from trinity.chains.full import FullChain  # noqa: F811

        return FullChain.configure(
            __name__=self.chain_name,
            vm_configuration=self.vm_configuration,
            chain_id=self.chain_id,
        )

    @property
    def light_chain_class(self) -> Type['LightDispatchChain']:
        from trinity.chains.light import LightDispatchChain  # noqa: F811

        return LightDispatchChain.configure(
            __name__=self.chain_name,
            vm_configuration=self.vm_configuration,
            chain_id=self.chain_id,
        )

    @classmethod
    def from_eip1085_genesis_config(cls,
                                    genesis_config: Dict[str, Any],
                                    chain_name: str=None,
                                    ) -> 'ChainConfig':
        genesis_data = extract_genesis_data(genesis_config)
        return cls(
            genesis_data=genesis_data,
            chain_name=chain_name,
        )

    @classmethod
    def from_preconfigured_network(cls,
                                   network_id: int) -> 'ChainConfig':
        genesis_config = _load_preconfigured_genesis_config(network_id)
        chain_name = _get_preconfigured_chain_name(network_id)
        return cls.from_eip1085_genesis_config(genesis_config, chain_name)

    @property
    def chain_id(self) -> int:
        return self.genesis_data.chain_id

    @property
    def genesis_params(self) -> GenesisParams:
        """
        Return the genesis configuation parsed from the genesis configuration file.
        """
        return self.genesis_data.params

    @property
    def genesis_state(self) -> Dict[Address, Account]:
        return self.genesis_data.state

    def initialize_chain(self,
                         base_db: BaseAtomicDB) -> 'FullChain':
        genesis_params = self.genesis_params.to_dict()
        genesis_state = {
            address: account.to_dict()
            for address, account
            in self.genesis_state.items()
        }
        return cast('FullChain', self.full_chain_class.from_genesis(
            base_db=base_db,
            genesis_params=genesis_params,
            genesis_state=genesis_state,
        ))

    @property
    def vm_configuration(self) -> VMConfiguration:
        """
        Return the vm configuration specifed from the genesis configuration file.
        """
        return self.genesis_data.vm_configuration


class TrinityConfig:
    _trinity_root_dir: Path = None

    _chain_config: ChainConfig = None

    _data_dir: Path = None
    _nodekey_path: Path = None
    _logfile_path: Path = None
    _nodekey = None
    _network_id: int = None

    port: int = None
    preferred_nodes: Tuple[KademliaNode, ...] = None

    bootstrap_nodes: Tuple[KademliaNode, ...] = None

    _genesis_config: Dict[str, Any] = None

    def __init__(self,
                 network_id: int,
                 genesis_config: Dict[str, Any]=None,
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

        if genesis_config is not None:
            self.genesis_config = genesis_config
        elif network_id in PRECONFIGURED_NETWORKS:
            self.genesis_config = _load_preconfigured_genesis_config(network_id)
        else:
            raise TypeError(
                "No `genesis_config` was provided and the `network_id` is not "
                "in the known preconfigured networks.  Cannot initialize "
                "ChainConfig"
            )

        if trinity_root_dir is not None:
            self.trinity_root_dir = trinity_root_dir

        if not preferred_nodes and self.network_id in DEFAULT_PREFERRED_NODES:
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

    def get_chain_config(self) -> ChainConfig:
        # the `ChainConfig` object cannot be pickled so we can't cache this
        # value since the TrinityConfig is sent across process boundaries.
        if self.network_id in PRECONFIGURED_NETWORKS:
            return ChainConfig.from_preconfigured_network(self.network_id)
        else:
            return ChainConfig.from_eip1085_genesis_config(self.genesis_config)

    @property
    def sync_mode(self) -> str:
        return self._sync_mode

    @sync_mode.setter
    def sync_mode(self, value: str) -> None:
        if value not in {SYNC_FULL, SYNC_LIGHT}:
            raise ValueError(f"Unknown sync mode: {value}")
        self._sync_mode = value

    @property
    def is_light_mode(self) -> bool:
        return self.sync_mode == SYNC_LIGHT

    @property
    def is_full_mode(self) -> bool:
        return self.sync_mode == SYNC_FULL

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
            raise ValueError(f"Unknown sync mode: {self.sync_mode}")

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
                f"`PrivateKey` instance: got {type(self._nodekey)}"
            )

    @classmethod
    def from_parser_args(cls, parser_args: argparse.Namespace) -> 'TrinityConfig':
        """
        Helper function for initializing from the namespace object produced by
        an ``argparse.ArgumentParser``
        """
        constructor_kwargs = construct_trinity_config_params(parser_args)
        return cls(**constructor_kwargs)

    @property
    def node_class(self) -> Type['Node']:
        """
        The ``Node`` class that trinity will use.
        """
        from trinity.nodes.full import FullNode
        from trinity.nodes.light import LightNode

        if self.is_full_mode:
            return FullNode
        elif self.is_light_mode:
            return LightNode
        else:
            raise NotImplementedError("Only full and light sync modes are supported")

    @contextmanager
    def process_id_file(self, process_name: str):  # type: ignore
        with PidFile(process_name, self.data_dir):
            yield
