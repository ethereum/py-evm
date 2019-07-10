import asyncio
import json
import logging
import pathlib
from typing import (
    Any,
    Callable,
    Tuple,
)

from eth_utils.toolz import curry

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

MAXIMUM_REQUEST_BYTES = 10000


@curry
async def connection_handler(execute_rpc: Callable[[Any], Any],
                             cancel_token: CancelToken,
                             reader: asyncio.StreamReader,
                             writer: asyncio.StreamWriter) -> None:
    """
    Catch fatal errors, log them, and close the connection
    """
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
                f"reached limit: {e.consumed} bytes, starting with '{request_bytes[:20]}'",
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
            result = await execute_rpc(request)
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


class IPCServer(BaseService):
    ipc_path = None
    rpc = None
    server = None

    def __init__(
            self,
            rpc: RPCServer,
            ipc_path: pathlib.Path,
            token: CancelToken = None,
            loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__(token=token, loop=loop)
        self.rpc = rpc
        self.ipc_path = ipc_path

    async def _run(self) -> None:
        self.server = await asyncio.start_unix_server(
            connection_handler(self.rpc.execute, self.cancel_token),
            str(self.ipc_path),
            loop=self.get_event_loop(),
            limit=MAXIMUM_REQUEST_BYTES,
        )
        self.logger.info('IPC started at: %s', self.ipc_path.resolve())
        await self.cancel_token.wait()

    async def _cleanup(self) -> None:
        self.server.close()
        await self.server.wait_closed()
        self.ipc_path.unlink()
