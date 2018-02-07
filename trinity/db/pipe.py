import logging
from multiprocessing.connection import (
    Listener,
    Client,
    wait,
)
import threading
import uuid
import time

from cytoolz import (
    concatv,
    curry,
)

from evm.db.backends.base import (
    BaseDB,
)


GET = 0
SET = 1
EXISTS = 2
DELETE = 3


@curry
def run_command(pipe_db, *params, command):
    req_id = uuid.uuid4()
    pipe_db.conn.send(list(concatv(
        [req_id, command],
        params,
    )))

    resp_id, response = pipe_db.conn.recv()
    if resp_id != req_id:
        raise ValueError('Request/Response id mismatch')

    if isinstance(response, Exception):
        raise response
    return response


class PipeDB(BaseDB):
    conn = None

    def __init__(self, ipc_path):
        self.conn = Client(ipc_path)

    get = run_command(command=GET)
    set = run_command(command=SET)
    exists = run_command(command=EXISTS)
    delete = run_command(command=DELETE)


def _accept_connections(listener, connections):
    logger = logging.getLogger('trinity.db.pipe._accept_connections')
    while True:
        try:
            conn = listener.accept()
            connections.append(conn)
        except OSError as err:
            # This means the listener has been closed so we gracefully exit the
            # loop, closing the thread.
            logger.info("Breaking connection loop due to error: %s", err)
            break


def db_server(db, ipc_path):
    logger = logging.getLogger('trinity.db.pipe.db_server')

    logger.info('Starting DB Process')
    with Listener(ipc_path) as listener:
        connections = []

        # We spin up a thread which accepts incomming connection requests and
        # adds them to the list of connection objects.
        thread = threading.Thread(
            target=_accept_connections,
            args=(listener, connections),
            daemon=True,
        )
        thread.start()

        while True:
            # If we have no connections, sleep for a moment, otherwise `wait`
            # blocks indefinitely on an empty list.
            if not connections:
                time.sleep(0.1)
                continue

            try:
                ready_connections = wait(connections)
                # For each connection which is ready to be read from, serve the
                # request
                for conn in ready_connections:
                    logger.debug('Serving db for connection: %s', conn)
                    try:
                        serve_db(db, conn)
                    except EOFError as err:
                        # This indicates the connection is closed, so we remove
                        # it from our connection list.
                        logger.debug('Removing closed database connection: %s', err)
                        connections.remove(conn)
            except KeyboardInterrupt:
                # Other processes can use `os.kill(pid, signal.SIGINT)` to
                # trigger the db_server to gracefully close it's connections
                # and exit.
                logger.info('KeyboardInterrupt: exiting db_server')
                for conn in connections:
                    conn.close()
                break

    # Join our thread which may take an extra moment to close after the
    # listener closes.
    thread.join()


def serve_db(db, conn):
    logger = logging.getLogger('trinity.db.pipe.serve_db')

    request = conn.recv()

    try:
        req_id, method, *params = request
    except (TypeError, ValueError) as err:
        # TypeError: request is non iterable
        # ValueError: request is less than length-2
        conn.send(err)

    try:
        if method == GET:
            key = params[0]
            logger.debug('GET: %s', key)

            try:
                conn.send([req_id, db.get(key)])
            except KeyError as err:
                conn.send([req_id, err])
        elif method == SET:
            key, value = params
            logger.debug('SET: %s -> %s', key, value)
            try:
                conn.send([req_id, db.set(key, value)])
            except KeyError as err:
                conn.send([req_id, err])
        elif method == EXISTS:
            key = params[0]
            logger.debug('EXISTS: %s', key)
            try:
                conn.send([req_id, db.exists(key)])
            except KeyError as err:
                conn.send([req_id, err])
        elif method == DELETE:
            key = params[0]
            logger.debug('DELETE: %s', key)
            try:
                conn.send([req_id, db.delete(key)])
            except KeyError as err:
                conn.send([req_id, err])
        else:
            logger.error("Got unknown method: %s: %s", method, params)
            conn.send(Exception("Invalid request method: {0}".format(method)))
    except Exception as err:
        # Push the failure out to whatever process was trying to interact
        # with the database.
        conn.send(err)
