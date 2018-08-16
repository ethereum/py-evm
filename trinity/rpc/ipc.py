import asyncio
import json
import logging
from multiprocessing.managers import (
    BaseManager,
    BaseProxy,
)
import pathlib
import tempfile
from typing import (
    Any,
    Callable,
    Tuple,
)

from cancel_token import (
    BaseCancelTokenManager,
    CancelTokenClient,
    CancelTokenProxy,
)

from cytoolz import curry

from cancel_token import (
    CancelToken,
    OperationCancelled,
)

from p2p.service import (
    BaseService,
)

from trinity.rpc.main import (
    RPCServer,
)
from trinity.utils.ipc import (
    wait_for_ipc,
    kill_process_gracefully,
)
from trinity.utils.mp import (
    ctx,
)
from trinity.utils.logging import (
    with_queued_logging,
)

MAXIMUM_REQUEST_BYTES = 10000


@curry
async def connection_handler(execute_rpc: Callable[[Any], Any],
                             cancel_token: CancelToken,
                             reader: asyncio.StreamReader,
                             writer: asyncio.StreamWriter) -> None:
    '''
    Catch fatal errors, log them, and close the connection
    '''
    logger = logging.getLogger('trinity.rpc.ipc')

    try:
        await connection_loop(execute_rpc, reader, writer, logger, cancel_token),
    except (ConnectionResetError, asyncio.IncompleteReadError):
        logger.debug("Client closed connection")
    except OperationCancelled:
        logger.debug("CancelToken triggered")
    except Exception:
        logger.exception("Unrecognized exception while handling requests")
    finally:
        writer.close()


async def connection_loop(execute_rpc: Callable[[Any], Any],
                          reader: asyncio.StreamReader,
                          writer: asyncio.StreamWriter,
                          logger: logging.Logger,
                          cancel_token: CancelToken) -> None:
    # TODO: we should look into using an io.StrinIO here for more efficient
    # writing to the end of the string.
    raw_request = ''
    while True:
        request_bytes = b''
        try:
            request_bytes = await cancel_token.cancellable_wait(reader.readuntil(b'}'))
        except asyncio.LimitOverrunError as e:
            logger.info("Client request was too long. Erasing buffer and restarting...")
            request_bytes = await cancel_token.cancellable_wait(reader.read(e.consumed))
            await cancel_token.cancellable_wait(write_error(
                writer,
                "reached limit: %d bytes, starting with '%s'" % (
                    e.consumed,
                    request_bytes[:20],
                ),
            ))
            continue

        raw_request += request_bytes.decode()

        bad_prefix, raw_request = strip_non_json_prefix(raw_request)
        if bad_prefix:
            logger.info("Client started request with non json data: %r", bad_prefix)
            await cancel_token.cancellable_wait(
                write_error(writer, 'Cannot parse json: ' + bad_prefix),
            )

        try:
            request = json.loads(raw_request)
        except json.JSONDecodeError:
            # invalid json request, keep reading data until a valid json is formed
            logger.debug("Invalid JSON, waiting for rest of message: %r", raw_request)
            continue

        # reset the buffer for the next message
        raw_request = ''

        if not request:
            logger.debug("Client sent empty request")
            await cancel_token.cancellable_wait(
                write_error(writer, 'Invalid Request: empty'),
            )
            continue

        try:
            result = execute_rpc(request)
        except Exception as e:
            logger.exception("Unrecognized exception while executing RPC")
            await cancel_token.cancellable_wait(
                write_error(writer, "unknown failure: " + str(e)),
            )
        else:
            writer.write(result.encode())

        await cancel_token.cancellable_wait(writer.drain())


def strip_non_json_prefix(raw_request: str) -> Tuple[str, str]:
    if raw_request and raw_request[0] != '{':
        prefix, bracket, rest = raw_request.partition('{')
        return prefix.strip(), bracket + rest
    else:
        return '', raw_request


async def write_error(writer: asyncio.StreamWriter, message: str) -> None:
    json_error = json.dumps({'error': message})
    writer.write(json_error.encode())
    await writer.drain()


def get_transient_ipc_path():
    with tempfile.NamedTemporaryFile(suffix='.ipc') as tmp_ipc_path:
        # we want a unique temporary file path but we also want it to not
        # exist yet so that the Manager class can create the IPC socket in
        # this location.  Thus, we wait till we exit the context so that
        # the filename gets cleaned up.
        pass
    return pathlib.Path(tmp_ipc_path.name)


class PeerPoolProxy(BaseProxy):
    _loop: asyncio.AbstractEventLoop = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            return asyncio.get_event_loop()
        else:
            return self._loop

    @loop.setter
    def loop(self, value: asyncio.AbstractEventLoop) -> None:
        self._loop = value

    _exposed_ = tuple()

    async def get_num_peers(self):
        return await self.loop.run_in_executor(
            None,
            self._callmethod,
            '__len__',
        )


class BasePeerPoolManager(BaseManager):
    pass


class PeerPoolClient(BasePeerPoolManager):
    pass


PeerPoolClient.register('get_peer_pool', proxytype=PeerPoolProxy)


def setup_peer_pool_manager(address, peer_pool):
    class PeerPoolManager(BasePeerPoolManager):
        pass

    PeerPoolManager.register('get_peer_pool', lambda: peer_pool, proxytype=PeerPoolProxy)

    manager = PeerPoolManager(address=str(address))
    return manager


def setup_peer_pool_client(address):
    client = PeerPoolClient(address=str(address))
    return client


def setup_cancel_token_manager(address, token):
    class CancelTokenManager(BaseCancelTokenManager):
        pass

    CancelTokenManager.register('get_cancel_token', lambda: token, proxytype=CancelTokenProxy)

    manager = CancelTokenManager(address=str(address))
    return manager


def setup_cancel_token_client(address):
    client = CancelTokenClient(address=str(address))
    return client


@with_queued_logging
def run_service_process(ServiceClass, args, kwargs):
    import logging
    logger = logging.getLogger('trinity')
    logger.info('IN run_service_process')
    service = ServiceClass(*args, **kwargs)

    loop = service.get_event_loop()
    loop.run_until_complete(service.run())


class IPCServiceWrapper(BaseService):
    def __init__(self,
                 chain_class,
                 peer_pool,
                 database_ipc_path: pathlib.Path,
                 jsonrpc_ipc_path: pathlib.Path,
                 token: CancelToken) -> None:
        super().__init__(token=token)
        self.database_ipc_path = database_ipc_path
        self.ipc_path = jsonrpc_ipc_path
        self.chain_class = chain_class
        self.token_manager = setup_cancel_token_manager(get_transient_ipc_path(), self.cancel_token)
        self.peer_pool_manager = setup_peer_pool_manager(get_transient_ipc_path(), peer_pool)

    async def _run_token_manager(self):
        server = self.token_manager.get_server()
        await self.loop.run_in_executor(None, server.serve_forever)

    async def _run_peer_pool_manager(self):
        server = self.peer_pool_manager.get_server()
        await self.loop.run_in_executor(None, server.serve_forever)

    async def _run(self):
        self.run_task(self._run_token_manager())
        token_manager_address = pathlib.Path(self.token_manager.address)
        self.run_task(self._run_peer_pool_manager())
        peer_pool_manager_address = pathlib.Path(self.peer_pool_manager.address)

        wait_for_ipc(token_manager_address)
        self.logger.info('Token Manager Address: %s', str(token_manager_address))
        wait_for_ipc(pathlib.Path(self.peer_pool_manager.address))
        self.logger.info('PeerPool Manager Address: %s', str(peer_pool_manager_address))

        from trinity.utils.logging import _log_queue as log_queue
        assert log_queue is not None
        self._proc = ctx.Process(
            target=run_service_process,
            args=(IPCServer, tuple(), dict(
                chain_class=self.chain_class,
                token_manager_address=self.token_manager.address,
                peer_pool_manager_address=self.peer_pool_manager.address,
                database_ipc_path=self.database_ipc_path,
                ipc_path=self.ipc_path,
            )),
            kwargs=dict(
                log_queue=log_queue,
                log_level=10,
            ),
        )
        self.logger.info('IPC PROC: STARTING')
        self._proc.start()
        await self.cancel_token.wait()
        self.logger.info('IPC PROC: FINISHED')

    async def _cleanup(self):
        kill_process_gracefully(self._proc, logger=self.logger)


class IPCServer(BaseService):
    ipc_path = None
    rpc = None
    server = None

    def __init__(
            self,
            chain_class,
            token_manager_address,
            peer_pool_manager_address,
            database_ipc_path: pathlib.Path,
            ipc_path: pathlib.Path) -> None:
        self.logger.info('IPC PROC: INITIALIZING')
        self.token_manager = setup_cancel_token_client(token_manager_address)
        self.token_manager.connect()
        token = self.token_manager.get_cancel_token()
        super().__init__(token=token)
        from trinity.nodes.base import create_db_manager
        # The core DB manager
        self.db_manager = create_db_manager(database_ipc_path)
        self.db_manager.connect()
        # Manager for the peer pool proxy
        self.peer_pool_manager = setup_peer_pool_client(peer_pool_manager_address)
        self.peer_pool_manager.connect()

        base_db = self.db_manager.get_db()

        self.rpc = RPCServer(
            chain=chain_class(base_db),
            peer_pool=self.peer_pool_manager.get_peer_pool(),
        )
        self.ipc_path = ipc_path
        self.logger.info('IPC PROC: INITIALIZED')

    async def _run(self) -> None:
        self.logger.info('IPC PROC: RUNNING')
        self.server = await self.wait(asyncio.start_unix_server(
            connection_handler(self.rpc.execute, self.cancel_token),
            str(self.ipc_path),
            loop=self.get_event_loop(),
            limit=MAXIMUM_REQUEST_BYTES,
        ))
        self.logger.info('IPC started at: %s', self.ipc_path.resolve())
        await self.cancel_token.wait()

    async def _cleanup(self) -> None:
        self.server.close()
        await self.wait(self.server.wait_closed())
        self.ipc_path.unlink()
