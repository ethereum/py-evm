import asyncio
import json
import logging

from cytoolz import curry

from p2p.cancel_token import (
    CancelToken,
    wait_with_token,
)
from p2p.exceptions import (
    OperationCancelled,
)


MAXIMUM_REQUEST_BYTES = 10000


@curry
async def connection_handler(execute_rpc, cancel_token, reader, writer):
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


async def connection_loop(execute_rpc, reader, writer, logger, cancel_token):
    # TODO: we should look into using an io.StrinIO here for more efficient
    # writing to the end of the string.
    raw_request = ''
    while True:
        request_bytes = b''
        try:
            request_bytes = await wait_with_token(reader.readuntil(b'}'), token=cancel_token)
        except asyncio.LimitOverrunError as e:
            logger.info("Client request was too long. Erasing buffer and restarting...")
            request_bytes = await wait_with_token(reader.read(e.consumed), token=cancel_token)
            await wait_with_token(write_error(
                writer,
                "reached limit: %d bytes, starting with '%s'" % (
                    e.consumed,
                    request_bytes[:20],
                ),
            ), token=cancel_token)
            continue

        raw_request += request_bytes.decode()

        bad_prefix, raw_request = strip_non_json_prefix(raw_request)
        if bad_prefix:
            logger.info("Client started request with non json data: %r", bad_prefix)
            await wait_with_token(
                write_error(writer, 'Cannot parse json: ' + bad_prefix),
                token=cancel_token,
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
            await wait_with_token(
                write_error(writer, 'Invalid Request: empty'),
                token=cancel_token,
            )
            continue

        try:
            result = execute_rpc(request)
        except Exception as e:
            logger.exception("Unrecognized exception while executing RPC")
            await wait_with_token(
                write_error(writer, "unknown failure: " + str(e)),
                token=cancel_token,
            )
        else:
            writer.write(result.encode())

        await wait_with_token(writer.drain(), token=cancel_token)


def strip_non_json_prefix(raw_request):
    if raw_request and raw_request[0] != '{':
        prefix, bracket, rest = raw_request.partition('{')
        return prefix.strip(), bracket + rest
    else:
        return '', raw_request


async def write_error(writer, message):
    json_error = json.dumps({'error': message}) + '\n'
    writer.write(json_error.encode())
    await writer.drain()


class IPCServer:
    cancel_token = None
    ipc_path = None
    rpc = None
    server = None

    def __init__(self, rpc, ipc_path):
        self.rpc = rpc
        self.ipc_path = ipc_path
        self.cancel_token = CancelToken('IPCServer')

    async def run(self, loop=None):
        self.server = await asyncio.start_unix_server(
            connection_handler(self.rpc.execute, self.cancel_token),
            self.ipc_path,
            loop=loop,
            limit=MAXIMUM_REQUEST_BYTES,
        )
        await self.cancel_token.wait()

    async def stop(self):
        self.cancel_token.trigger()
        self.server.close()
        await self.server.wait_closed()
