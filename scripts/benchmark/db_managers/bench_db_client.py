import argparse
import logging
import multiprocessing
import os
import pathlib
import random
import signal
import sys
import tempfile
import time

from eth.db.backends.level import LevelDB

from trinity.db.manager import (
    DBManager,
    DBClient,
)

logger = logging.getLogger('trinity.scripts.benchmark')
logger.setLevel(logging.INFO)

handler_stream = logging.StreamHandler(sys.stderr)
handler_stream.setLevel(logging.INFO)

logger.addHandler(handler_stream)


def random_bytes(num):
    return random.getrandbits(8 * num).to_bytes(num, 'little')


def run_server(ipc_path):
    with tempfile.TemporaryDirectory() as db_path:
        db = LevelDB(db_path=db_path)
        manager = DBManager(db)

        with manager.run(ipc_path):
            try:
                manager.wait_stopped()
            except KeyboardInterrupt:
                pass

        ipc_path.unlink()


def run_client(ipc_path, client_id, num_operations):
    key_values = {
        random_bytes(32): random_bytes(256)
        for i in range(num_operations)
    }

    db_client = DBClient.connect(ipc_path)

    start = time.perf_counter()
    for key, value in key_values.items():
        db_client.set(key, value)
        db_client.get(key)
    end = time.perf_counter()
    duration = end - start

    logger.info(
        "Client %d: %d get-set per second",
        client_id,
        num_operations / duration,
    )


parser = argparse.ArgumentParser(description='Database Manager Benchmark')
parser.add_argument(
    '--num-clients',
    type=int,
    required=False,
    default=1,
    help=(
        "Number of concurrent clients that should access the database"
    ),
)
parser.add_argument(
    '--num-operations',
    type=int,
    required=False,
    default=10000,
    help=(
        "Number of set+get operations that should be performed for each client"
    ),
)


if __name__ == '__main__':
    args = parser.parse_args()
    logger.info(
        "Running database manager benchmark:\n - %d client(s)\n - %d get-set operations\n*****************************\n",  # noqa: E501
        args.num_clients,
        args.num_operations,
    )
    with tempfile.TemporaryDirectory() as ipc_base_dir:
        ipc_path = pathlib.Path(ipc_base_dir) / 'db.ipc'

        server = multiprocessing.Process(target=run_server, args=[ipc_path])

        clients = [
            multiprocessing.Process(
                target=run_client,
                args=(ipc_path, client_id, args.num_operations),
            ) for client_id in range(args.num_clients)
        ]
        server.start()
        for client in clients:
            client.start()
        for client in clients:
            client.join(600)

        os.kill(server.pid, signal.SIGINT)
        server.join(1)
    logger.info('\n')
