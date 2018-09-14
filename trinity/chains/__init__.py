# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseManager,
    BaseProxy,
)
import inspect
import os
import traceback
from types import TracebackType
from typing import (
    Any,
    Callable,
    List,
    Type
)

from eth import MainnetChain, RopstenChain
from eth.chains.base import (
    BaseChain
)
from eth.chains.mainnet import (
    MAINNET_GENESIS_HEADER,
    MAINNET_NETWORK_ID,
)
from eth.chains.ropsten import (
    ROPSTEN_GENESIS_HEADER,
    ROPSTEN_NETWORK_ID,
)
from eth.db.backends.base import BaseAtomicDB
from eth.exceptions import CanonicalHeadNotFound

from p2p import ecies

from trinity.exceptions import (
    MissingPath,
)
from trinity.config import ChainConfig
from trinity.db.base import DBProxy
from trinity.db.chain import AsyncChainDB, ChainDBProxy
from trinity.db.header import (
    AsyncHeaderDB,
    AsyncHeaderDBProxy,
)
from trinity.utils.filesystem import (
    is_under_path,
)
from trinity.utils.mp import (
    async_method,
    sync_method,
)


from .header import (
    AsyncHeaderChain,
    AsyncHeaderChainProxy,
)


def is_data_dir_initialized(chain_config: ChainConfig) -> bool:
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

    if not chain_config.logfile_path.parent.exists():
        return False
    elif not chain_config.logfile_path.exists():
        return False

    if chain_config.nodekey_path is None:
        # has an explicitely defined nodekey
        pass
    elif not os.path.exists(chain_config.nodekey_path):
        return False

    if chain_config.nodekey is None:
        return False

    return True


def is_database_initialized(chaindb: AsyncChainDB) -> bool:
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # empty chain database
        return False
    else:
        return True


def initialize_data_dir(chain_config: ChainConfig) -> None:
    should_create_data_dir = (
        not chain_config.data_dir.exists() and
        is_under_path(chain_config.trinity_root_dir, chain_config.data_dir)
    )
    if should_create_data_dir:
        chain_config.data_dir.mkdir(parents=True, exist_ok=True)
    elif not chain_config.data_dir.exists():
        # we don't lazily create the base dir for non-default base directories.
        raise MissingPath(
            "The base chain directory provided does not exist: `{0}`".format(
                chain_config.data_dir,
            ),
            chain_config.data_dir
        )

    # Logfile
    should_create_logdir = (
        not chain_config.logdir_path.exists() and
        is_under_path(chain_config.trinity_root_dir, chain_config.logdir_path)
    )
    if should_create_logdir:
        chain_config.logdir_path.mkdir(parents=True, exist_ok=True)
        chain_config.logfile_path.touch()
    elif not chain_config.logdir_path.exists():
        # we don't lazily create the base dir for non-default base directories.
        raise MissingPath(
            "The base logging directory provided does not exist: `{0}`".format(
                chain_config.logdir_path,
            ),
            chain_config.logdir_path
        )

    # Chain data-dir
    os.makedirs(chain_config.database_dir, exist_ok=True)

    # Nodekey
    if chain_config.nodekey is None:
        nodekey = ecies.generate_privkey()
        with open(chain_config.nodekey_path, 'wb') as nodekey_file:
            nodekey_file.write(nodekey.to_bytes())


def initialize_database(chain_config: ChainConfig, chaindb: AsyncChainDB) -> None:
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        if chain_config.network_id == ROPSTEN_NETWORK_ID:
            # We're starting with a fresh DB.
            chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
        elif chain_config.network_id == MAINNET_NETWORK_ID:
            chaindb.persist_header(MAINNET_GENESIS_HEADER)
        else:
            # TODO: add genesis data to ChainConfig and if it's present, use it
            # here to initialize the chain.
            raise NotImplementedError(
                "Only the mainnet and ropsten chains are currently supported"
            )


class TracebackRecorder:
    """
    Wrap the given instance, delegating all attribute accesses to it but if any method call raises
    an exception it is converted into a ChainedExceptionWithTraceback that uses exception chaining
    in order to retain the traceback that led to the exception in the remote process.
    """

    def __init__(self, obj: Any) -> None:
        self.obj = obj

    def __dir__(self) -> List[str]:
        return dir(self.obj)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.obj, name)
        if not inspect.ismethod(attr):
            return attr
        else:
            return record_traceback_on_error(attr)


def record_traceback_on_error(attr: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return attr(*args, **kwargs)
        except Exception as e:
            # This is a bit of a hack based on https://bugs.python.org/issue13831 to record the
            # original traceback (as a string, which is picklable unlike traceback instances) in
            # the exception that will be sent to the remote process.
            raise ChainedExceptionWithTraceback(e, e.__traceback__)

    return wrapper


class RemoteTraceback(Exception):

    def __init__(self, tb: str) -> None:
        self.tb = tb

    def __str__(self) -> str:
        return self.tb


class ChainedExceptionWithTraceback(Exception):

    def __init__(self, exc: Exception, tb: TracebackType) -> None:
        self.tb = '\n"""\n%s"""' % ''.join(traceback.format_exception(type(exc), exc, tb))
        self.exc = exc

    def __reduce__(self) -> Any:
        return rebuild_exc, (self.exc, self.tb)


def rebuild_exc(exc, tb):  # type: ignore
    exc.__cause__ = RemoteTraceback(tb)
    return exc


def get_chaindb_manager(chain_config: ChainConfig, base_db: BaseAtomicDB) -> BaseManager:
    chaindb = AsyncChainDB(base_db)
    chain_class: Type[BaseChain]
    if not is_database_initialized(chaindb):
        initialize_database(chain_config, chaindb)
    if chain_config.network_id == MAINNET_NETWORK_ID:
        chain_class = MainnetChain
    elif chain_config.network_id == ROPSTEN_NETWORK_ID:
        chain_class = RopstenChain
    else:
        raise NotImplementedError(
            "Only the mainnet and ropsten chains are currently supported"
        )
    chain = chain_class(base_db)

    headerdb = AsyncHeaderDB(base_db)
    header_chain = AsyncHeaderChain(base_db)

    class DBManager(BaseManager):
        pass

    # Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
    # https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
    DBManager.register(  # type: ignore
        'get_db', callable=lambda: TracebackRecorder(base_db), proxytype=DBProxy)

    DBManager.register(  # type: ignore
        'get_chaindb',
        callable=lambda: TracebackRecorder(chaindb),
        proxytype=ChainDBProxy,
    )
    DBManager.register(  # type: ignore
        'get_chain', callable=lambda: TracebackRecorder(chain), proxytype=ChainProxy)

    DBManager.register(  # type: ignore
        'get_headerdb',
        callable=lambda: TracebackRecorder(headerdb),
        proxytype=AsyncHeaderDBProxy,
    )
    DBManager.register(  # type: ignore
        'get_header_chain',
        callable=lambda: TracebackRecorder(header_chain),
        proxytype=AsyncHeaderChainProxy,
    )

    manager = DBManager(address=str(chain_config.database_ipc_path))  # type: ignore
    return manager


class ChainProxy(BaseProxy):
    coro_import_block = async_method('import_block')
    coro_validate_chain = async_method('validate_chain')
    coro_validate_receipt = async_method('validate_receipt')
    get_vm_configuration = sync_method('get_vm_configuration')
    get_vm_class = sync_method('get_vm_class')
    get_vm_class_for_block_number = sync_method('get_vm_class_for_block_number')
