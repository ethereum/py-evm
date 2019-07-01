from abc import (
    ABC,
    abstractmethod,
)
import argparse
from contextlib import (
    contextmanager,
)
from enum import (
    Enum,
    auto,
)
import json
from pathlib import (
    Path,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    NamedTuple,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from eth.db.backends.base import (
    BaseAtomicDB,
)
from eth.typing import (
    VMConfiguration,
)
from eth_keys import (
    keys,
)
from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    Address,
    BLSPubkey,
)

from eth2.beacon.chains.testnet import (
    TestnetChain,
)
from eth2.beacon.genesis import (
    get_genesis_block,
)
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Timestamp,
)
from eth2.configs import (
    Eth2GenesisConfig,
)
from p2p.constants import (
    MAINNET_BOOTNODES,
    ROPSTEN_BOOTNODES,
)
from p2p.kademlia import (
    Node as KademliaNode,
)
from trinity._utils.chains import (
    construct_trinity_config_params,
    get_data_dir_for_network_id,
    get_database_socket_path,
    get_jsonrpc_socket_path,
    get_nodekey_path,
    load_nodekey,
)
from trinity._utils.eip1085 import (
    Account,
    GenesisData,
    GenesisParams,
    extract_genesis_data,
)
from trinity._utils.filesystem import (
    PidFile,
)
from trinity._utils.xdg import (
    get_xdg_trinity_root,
)
from trinity.constants import (
    ASSETS_DIR,
    DEFAULT_PREFERRED_NODES,
    IPC_DIR,
    LOG_DIR,
    LOG_FILE,
    MAINNET_NETWORK_ID,
    PID_DIR,
    ROPSTEN_NETWORK_ID,
    SYNC_LIGHT,
)
from trinity.plugins.eth2.beacon.utils import (
    extract_genesis_state_from_stream,
    extract_privkeys_from_dir,
)
from trinity.plugins.eth2.constants import (
    VALIDATOR_KEY_DIR,
)
from trinity.plugins.eth2.network_generator.constants import (
    GENESIS_FILE,
)


if TYPE_CHECKING:
    # avoid circular import
    from trinity.nodes.base import Node  # noqa: F401
    from trinity.chains.full import FullChain  # noqa: F401
    from trinity.chains.light import LightDispatchChain  # noqa: F401
    from eth2.beacon.chains.base import BeaconChain  # noqa: F401
    from eth2.beacon.state_machines.base import BaseBeaconStateMachine  # noqa: F401

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


class Eth1ChainConfig:
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
                                    ) -> 'Eth1ChainConfig':
        genesis_data = extract_genesis_data(genesis_config)
        return cls(
            genesis_data=genesis_data,
            chain_name=chain_name,
        )

    @classmethod
    def from_preconfigured_network(cls,
                                   network_id: int) -> 'Eth1ChainConfig':
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


TAppConfig = TypeVar('TAppConfig', bound='BaseAppConfig')


class TrinityConfig:
    """
    The :class:`~trinity.config.TrinityConfig` holds all base configurations that are generic
    enough to be shared across the different runtime modes that are available. It also gives access
    to the more specific application configurations derived from
    :class:`~trinity.config.BaseAppConfig`.

    This API is exposed to :class:`~trinity.extensibility.plugin.BasePlugin`
    """

    _trinity_root_dir: Path = None

    _chain_config: Eth1ChainConfig = None

    _data_dir: Path = None
    _nodekey_path: Path = None
    _logfile_path: Path = None
    _nodekey = None
    _network_id: int = None

    port: int = None
    preferred_nodes: Tuple[KademliaNode, ...] = None

    bootstrap_nodes: Tuple[KademliaNode, ...] = None

    _genesis_config: Dict[str, Any] = None

    _app_configs: Dict[Type['BaseAppConfig'], 'BaseAppConfig'] = None

    def __init__(self,
                 network_id: int,
                 app_identifier: str="",
                 genesis_config: Dict[str, Any]=None,
                 max_peers: int=25,
                 trinity_root_dir: str=None,
                 data_dir: str=None,
                 nodekey_path: str=None,
                 nodekey: PrivateKey=None,
                 port: int=30303,
                 use_discv5: bool = False,
                 preferred_nodes: Tuple[KademliaNode, ...]=None,
                 bootstrap_nodes: Tuple[KademliaNode, ...]=None) -> None:
        self.app_identifier = app_identifier
        self.network_id = network_id
        self.max_peers = max_peers
        self.port = port
        self.use_discv5 = use_discv5
        self._app_configs = {}

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
                self.bootstrap_nodes = tuple()
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

    @property
    def app_suffix(self) -> str:
        """
        Return the suffix that Trinity uses to derive various application directories depending
        on the current mode of operation (e.g. ``eth1`` or ``beacon`` to derive
        ``<trinity-root-dir>/mainnet/logs-eth1`` vs ``<trinity-root-dir>/mainnet/logs-beacon``)
        """
        return "" if len(self.app_identifier) == 0 else f"-{self.app_identifier}"

    @property
    def logfile_path(self) -> Path:
        """
        Return the path to the log file.
        """
        return self.log_dir / LOG_FILE

    @property
    def log_dir(self) -> Path:
        """
        Return the path of the directory where all log files are stored.
        """
        return self.with_app_suffix(self.data_dir / LOG_DIR)

    @property
    def trinity_root_dir(self) -> Path:
        """
        Base directory that all trinity data is stored under.

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
    def database_ipc_path(self) -> Path:
        """
        Return the path for the database IPC socket connection.
        """
        return get_database_socket_path(self.ipc_dir)

    @property
    def ipc_dir(self) -> Path:
        """
        Return the base directory for all open IPC files.
        """
        return self.with_app_suffix(self.data_dir / IPC_DIR)

    @property
    def pid_dir(self) -> Path:
        """
        Return the base directory for all PID files.
        """
        return self.with_app_suffix(self.data_dir / PID_DIR)

    @property
    def jsonrpc_ipc_path(self) -> Path:
        """
        Return the path for the JSON-RPC server IPC socket.
        """
        return get_jsonrpc_socket_path(self.ipc_dir)

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
        """
        The :class:`~eth_keys.datatypes.PrivateKey` which trinity uses to derive the
        public key needed to identify itself on the network.
        """
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

    @contextmanager
    def process_id_file(self, process_name: str):  # type: ignore
        """
        Context manager API to generate process identification files (pid) in the current
        :meth:`pid_dir`.

        .. code-block:: python

            trinity_config.process_id_file('networking'):
                ... # pid file sitting in pid directory while process is running
            ... # pid file cleaned up
        """
        with PidFile(process_name, self.pid_dir):
            yield

    @classmethod
    def from_parser_args(cls,
                         parser_args: argparse.Namespace,
                         app_identifier: str,
                         app_config_types: Iterable[Type['BaseAppConfig']]) -> 'TrinityConfig':
        """
        Initialize a :class:`~trinity.config.TrinityConfig` from the namespace object produced by
        an :class:`~argparse.ArgumentParser`.
        """
        constructor_kwargs = construct_trinity_config_params(parser_args)
        trinity_config = cls(app_identifier=app_identifier, **constructor_kwargs)

        trinity_config.initialize_app_configs(parser_args, app_config_types)

        return trinity_config

    def initialize_app_configs(self,
                               parser_args: argparse.Namespace,
                               app_config_types: Iterable[Type['BaseAppConfig']]) -> None:
        """
        Initialize :class:`~trinity.config.BaseAppConfig` instances for the passed
        ``app_config_types`` based on the ``parser_args`` and the existing
        :class:`~trinity.config.TrintiyConfig` instance.
        """
        for app_config_type in app_config_types:
            self.add_app_config(app_config_type.from_parser_args(parser_args, self))

    def add_app_config(self, app_config: 'BaseAppConfig') -> None:
        """
        Register the given ``app_config``.
        """
        self._app_configs[type(app_config)] = app_config

    def has_app_config(self, app_config_type: Type['BaseAppConfig']) -> bool:
        """
        Check if a :class:`~trinity.config.BaseAppConfig` instance exists that matches the given
        ``app_config_type``.
        """
        return app_config_type in self._app_configs.keys()

    def get_app_config(self, app_config_type: Type[TAppConfig]) -> TAppConfig:
        """
        Return the registered :class:`~trinity.config.BaseAppConfig` instance that matches
        the given ``app_config_type``.
        """
        # We want this API to return the specific type of the app config that is requested.
        # Our backing field only knows that it is holding `BaseAppConfig`'s but not concrete types
        return cast(TAppConfig, self._app_configs[app_config_type])

    def with_app_suffix(self, path: Path) -> Path:
        """
        Return a :class:`~pathlib.Path` that matches the given ``path`` plus the :meth:`app_suffix`
        """
        return path.with_name(path.name + self.app_suffix)


class BaseAppConfig(ABC):

    def __init__(self, trinity_config: TrinityConfig):
        self.trinity_config = trinity_config

    @classmethod
    @abstractmethod
    def from_parser_args(cls,
                         args: argparse.Namespace,
                         trinity_config: TrinityConfig) -> 'BaseAppConfig':
        """
        Initialize from the namespace object produced by
        an ``argparse.ArgumentParser`` and the :class:`~trinity.config.TrinityConfig`
        """
        pass


class Eth1DbMode(Enum):

    FULL = auto()
    LIGHT = auto()


class Eth1AppConfig(BaseAppConfig):

    def __init__(self, trinity_config: TrinityConfig, sync_mode: str):
        super().__init__(trinity_config)
        self.trinity_config = trinity_config
        self._sync_mode = sync_mode

    @classmethod
    def from_parser_args(cls,
                         args: argparse.Namespace,
                         trinity_config: TrinityConfig) -> 'BaseAppConfig':
        """
        Initialize from the namespace object produced by
        an ``argparse.ArgumentParser`` and the :class:`~trinity.config.TrinityConfig`
        """
        return cls(trinity_config, args.sync_mode)

    @property
    def database_dir(self) -> Path:
        """
        Path where the chain database is stored.

        This is resolved relative to the ``data_dir``
        """
        path = self.trinity_config.data_dir / DATABASE_DIR_NAME
        if self.database_mode is Eth1DbMode.LIGHT:
            return self.trinity_config.with_app_suffix(path) / "light"
        elif self.database_mode is Eth1DbMode.FULL:
            return self.trinity_config.with_app_suffix(path) / "full"
        else:
            raise Exception(f"Unsupported Database Mode: {self.database_mode}")

    @property
    def database_mode(self) -> Eth1DbMode:
        """
        Return the :class:`~trinity.config.Eth1DbMode` for the currently used database
        """
        if self.sync_mode == SYNC_LIGHT:
            return Eth1DbMode.LIGHT
        else:
            return Eth1DbMode.FULL

    def get_chain_config(self) -> Eth1ChainConfig:
        """
        Return the :class:`~trinity.config.Eth1ChainConfig` either derived from the ``network_id``
        or a custom genesis file.
        """
        # the `ChainConfig` object cannot be pickled so we can't cache this
        # value since the TrinityConfig is sent across process boundaries.
        if self.trinity_config.network_id in PRECONFIGURED_NETWORKS:
            return Eth1ChainConfig.from_preconfigured_network(self.trinity_config.network_id)
        else:
            return Eth1ChainConfig.from_eip1085_genesis_config(self.trinity_config.genesis_config)

    @property
    def node_class(self) -> Type['Node[Any]']:
        """
        Return the ``Node`` class that trinity uses.
        """
        from trinity.nodes.full import FullNode
        from trinity.nodes.light import LightNode

        if self.database_mode is Eth1DbMode.FULL:
            return FullNode
        elif self.database_mode is Eth1DbMode.LIGHT:
            return LightNode
        else:
            raise NotImplementedError(f"Database mode {self.database_mode} not supported")

    @property
    def sync_mode(self) -> str:
        """
        Return the currently used sync mode
        """
        return self._sync_mode


class BeaconGenesisData(NamedTuple):
    """
    Use this data to initialize BeaconChainConfig
    """
    genesis_time: Timestamp
    # TODO: Should come from eth2.beacon.genesis.get_genesis_beacon_state
    state: BeaconState
    # TODO: Trinity should have no knowledge of validators' private keys
    validator_keymap: Dict[BLSPubkey, int]
    # TODO: Maybe Validator deposit data


class BeaconChainConfig:
    network_id: int
    genesis_data: BeaconGenesisData
    _chain_name: str
    _beacon_chain_class: Type['BeaconChain'] = None
    _genesis_config: Eth2GenesisConfig = None

    def __init__(self,
                 chain_name: str=None,
                 genesis_data: BeaconGenesisData=None) -> None:

        self.network_id = 5567
        self.genesis_data = genesis_data

        self._chain_name = chain_name

    @property
    def genesis_config(self) -> Eth2GenesisConfig:
        if self._genesis_config is None:
            self._genesis_config = Eth2GenesisConfig(
                self.beacon_chain_class.get_genesis_state_machine_class().config,
            )

        return self._genesis_config

    @property
    def chain_name(self) -> str:
        if self._chain_name is None:
            return "CustomBeaconChain"
        else:
            return self._chain_name

    @property
    def beacon_chain_class(self) -> Type['BeaconChain']:
        if self._beacon_chain_class is None:
            # TODO: we should be able to customize configs for tests/ instead of using the configs
            #   from `TestnetChain`
            self._beacon_chain_class = TestnetChain.configure(
                __name__=self.chain_name,
            )
        return self._beacon_chain_class

    @classmethod
    def from_genesis_files(cls,
                           root_dir: Path,
                           chain_name: str=None) -> 'BeaconChainConfig':
        # parse `genesis_state`
        genesis_file_path = root_dir / GENESIS_FILE
        state = extract_genesis_state_from_stream(genesis_file_path)
        # parse privkeys and build `validator_keymap`
        keys_path = root_dir / VALIDATOR_KEY_DIR
        validator_keymap = extract_privkeys_from_dir(keys_path)
        # set `genesis_data`
        genesis_data = BeaconGenesisData(
            genesis_time=state.genesis_time,
            state=state,
            validator_keymap=validator_keymap,
        )
        return cls(
            genesis_data=genesis_data,
            chain_name=chain_name,
        )

    def initialize_chain(self,
                         base_db: BaseAtomicDB) -> 'BeaconChain':
        chain_class = self.beacon_chain_class
        state = self.genesis_data.state
        block = get_genesis_block(
            genesis_state_root=state.root,
            block_class=chain_class.get_genesis_state_machine_class().block_class,
        )
        return chain_class.from_genesis(
            base_db=base_db,
            genesis_state=state,
            genesis_block=block,
            genesis_config=self.genesis_config,
        )


class BeaconAppConfig(BaseAppConfig):

    @classmethod
    def from_parser_args(cls,
                         args: argparse.Namespace,
                         trinity_config: TrinityConfig) -> 'BaseAppConfig':
        """
        Initialize from the namespace object produced by
        an ``argparse.ArgumentParser`` and the :class:`~trinity.config.TrinityConfig`
        """
        if args is not None:
            # This is quick and dirty way to get bootstrap_nodes
            trinity_config.bootstrap_nodes = tuple(
                KademliaNode.from_uri(enode) for enode in args.bootstrap_nodes.split(',')
            ) if args.bootstrap_nodes is not None else tuple()
            trinity_config.preferred_nodes = tuple(
                KademliaNode.from_uri(enode) for enode in args.preferred_nodes.split(',')
            ) if args.preferred_nodes is not None else tuple()
        return cls(trinity_config)

    @property
    def database_dir(self) -> Path:
        """
        Return the path where the chain database is stored.

        This is resolved relative to the ``data_dir``
        """
        path = self.trinity_config.data_dir / DATABASE_DIR_NAME
        return self.trinity_config.with_app_suffix(path) / "full"

    def get_chain_config(self) -> BeaconChainConfig:
        """
        Return the :class:`~trinity.config.BeaconChainConfig` that is derived from the genesis file
        """
        return BeaconChainConfig.from_genesis_files(
            root_dir=self.trinity_config.trinity_root_dir,
            chain_name="TestnetChain",
        )
