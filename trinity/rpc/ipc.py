import asyncio
import json
import logging
import os

from cytoolz import curry

from trinity.rpc.main import RPCServer


MAXIMUM_REQUEST_BYTES = 10000


@curry
async def connection_handler(execute_rpc, reader, writer):
    '''
    Catch fatal errors, log them, and close the connection
    '''
    logger = logging.getLogger('trinity.rpc.ipc')
    try:
        await connection_loop(execute_rpc, reader, writer, logger)
    except (ConnectionResetError, asyncio.IncompleteReadError):
        logger.debug("Client closed connection")
    except Exception:
        logger.exception("Unrecognized exception while handling requests")
    finally:
        writer.close()


async def connection_loop(execute_rpc, reader, writer, logger):
    raw_request = ''
    while True:
        request_bytes = b''
        try:
            request_bytes = await reader.readuntil(b'}')
        except asyncio.LimitOverrunError as e:
            logger.info("Client request was too long. Erasing buffer and restarting...")
            request_bytes = await reader.read(e.consumed)
            await write_error(writer, "reached limit: %d bytes, starting with '%s'" % (
                e.consumed,
                request_bytes[:20],
            ))
            continue

        raw_request += request_bytes.decode()

        bad_prefix, raw_request = strip_non_json_prefix(raw_request)
        if bad_prefix:
            logger.info("Client started request with non json data: %r", bad_prefix)
            await write_error(writer, 'Cannot parse json: ' + bad_prefix)

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
            continue

        try:
            result = execute_rpc(request)
        except Exception as e:
            logger.exception("Unrecognized exception while executing RPC")
            await write_error(writer, "unknown failure: " + str(e))
        else:
            writer.write(result.encode())

        await writer.drain()


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


def start(path, chain=None, loop=None):
    '''
    :returns: initialized server
    :rtype: asyncio.Server
    '''
    if loop is None:
        loop = asyncio.get_event_loop()
    rpc = RPCServer(chain)
    server = loop.run_until_complete(asyncio.start_unix_server(
        connection_handler(rpc.execute),
        path,
        loop=loop,
        limit=MAXIMUM_REQUEST_BYTES,
    ))
    return server


def run_until_interrupt(server, loop=None):
    logger = logging.getLogger('trinity.rpc.ipc')
    if loop is None:
        loop = asyncio.get_event_loop()
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.debug('Server closed with Keyboard Interrupt')
    finally:
        loop.close()


def run_ipc_server(ipc_path, chain=None, loop=None):
    server = start(ipc_path, chain, loop)
    run_until_interrupt(server, loop)
    if os.path.exists(ipc_path):
        os.remove(ipc_path)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logging.getLogger('trinity.rpc.ipc').setLevel(logging.DEBUG)

    run_ipc_server('/tmp/test.ipc')
