import functools
from multiprocessing.connection import (
    Listener,
    Client,
    wait,
)
import operator
import os
import signal
import threading
import time
import uuid


def wait_for_ipc(ipc_path, timeout=1):
    start_at = time.time()
    while time.time() - start_at < timeout:
        if os.path.exists(ipc_path):
            break
        time.sleep(0.05)


def kill_processes_gracefully(*processes, logger=None, SIGINT_timeout=5, SIGTERM_timeout=3):
    try:
        for process in processes:
            if not process.is_alive():
                continue
            os.kill(process.pid, signal.SIGINT)
            process.join(SIGINT_timeout)
    except KeyboardInterrupt:
        if logger is not None:
            logger.info(
                "Waiting for processes to terminate.  You may force termination "
                "with CTRL+C two more times."
            )

    try:
        for process in processes:
            if not process.is_alive():
                continue
            os.kill(process.pid, signal.SIGTERM)
            process.join(SIGTERM_timeout)
    except KeyboardInterrupt:
        if logger is not None:
            logger.info(
                "Waiting for processes to terminate.  You may force termination "
                "with CTRL+C one more time."
            )

    for process in processes:
        if not process.is_alive():
            continue
        os.kill(process.pid, signal.SIGKILL)


def accept_connections(listener, connections, logger):
    if logger:
        logger.debug("Starting connection acceptance loop")

    while True:
        try:
            conn = listener.accept()
            if logger:
                logger.debug('Accepted incoming connection: %s', conn)
            connections.append(conn)
        except OSError as err:
            # This typically means the listener has been closed so we
            # gracefully exit the loop, closing the thread.
            if logger:
                logger.debug("Breaking connection acceptance loop due to error: %s", err)
            break
        except Exception:
            if logger:
                logger.exception("Error during connection acceptance loop")
            raise


def ipc_operator(operator_fn, *op_args, **op_kwargs):
    def inner(obj, *fn_args, **fn_kwargs):
        req_id = uuid.uuid4()
        obj.connection.send([
            req_id,
            operator_fn(*op_args, *fn_args, **op_kwargs, **fn_kwargs),
        ])
        resp_id, response = obj.connection.recv()
        if resp_id != req_id:
            raise ValueError(
                "Request/Response id mismatch.\n"
                "Expected: {0}\n"
                "Got: {1}".format(req_id, resp_id)
            )

        if isinstance(response, Exception):
            raise response
        return response
    return inner


IPCMethod = functools.partial(ipc_operator, operator.methodcaller)


class ObjectOverIPC:
    connection = None

    def __init__(self, ipc_path):
        self.connection = Client(ipc_path)


def handle_obj_over_ipc_connection(obj, connection, logger):
    request = connection.recv()

    try:
        req_id, operator_fn = request
    except (TypeError, ValueError) as err:
        # TypeError: request is non iterable
        # ValueError: request is less than length-2
        connection.send([None, err])

    try:
        connection.send([req_id, operator_fn(obj)])
    except Exception as err:
        connection.send([req_id, err])


def serve_object_over_ipc(obj,
                          ipc_path,
                          handle_connection_fn=handle_obj_over_ipc_connection,
                          logger=None):
    if logger:
        logger.info('Starting server')

    if os.path.exists(ipc_path):
        raise OSError(
            "Found existing IPC socket at {0}.  Either there is another running "
            "process using this socket or the previous running process may have "
            "failed to failed to shut down cleanly.  If there are no other "
            "processes running then removing this file is **probably** the way "
            "to fix this."
        )

    with Listener(ipc_path) as listener:
        connections = []

        # We spin up a thread which accepts incomming connection requests and
        # adds them to the list of connection objects.
        thread = threading.Thread(
            target=accept_connections,
            args=(listener, connections, logger),
            daemon=True,
        )
        thread.start()

        while True:
            try:
                # If we have no connections, sleep for a moment, otherwise `wait`
                # blocks indefinitely on an empty list.
                if not connections:
                    time.sleep(0.1)
                    continue

                ready_connections = wait(connections)
                # For each connection which is ready to be read from, serve the
                # request
                for conn in ready_connections:
                    if logger:
                        logger.debug('Serving db for connection: %s', conn)
                    try:
                        handle_connection_fn(obj, conn, logger)
                    except EOFError as err:
                        # This indicates the connection is closed, so we remove
                        # it from our connection list.
                        if logger:
                            logger.debug('Removing closed database connection: %s', err)
                        connections.remove(conn)
            except KeyboardInterrupt:
                # Other processes can use `os.kill(pid, signal.SIGINT)` to
                # trigger the db_server to gracefully close it's connections
                # and exit.
                if logger:
                    logger.info('Closing %s open connections', len(connections))
                for conn in connections:
                    conn.close()
                break
        if logger:
            logger.info('Shutting down server')

    # Join our thread which may take an extra moment to close after the
    # listener closes.
    thread.join()
