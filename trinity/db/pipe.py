import logging
import uuid

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
    pipe_db.pipe.send(list(concatv(
        [req_id, command],
        params,
    )))

    resp_id, response = pipe_db.pipe.recv()
    if resp_id != req_id:
        raise ValueError('Request/Response id mismatch')

    if isinstance(response, Exception):
        raise response
    return response


class PipeDB(BaseDB):
    pipe = None

    def __init__(self, pipe):
        self.pipe = pipe

    get = run_command(command=GET)
    set = run_command(command=SET)
    exists = run_command(command=EXISTS)
    delete = run_command(command=DELETE)


def db_over_pipe(db, pipe):
    logger = logging.getLogger('trinity.main.db_process')

    logger.info('Starting DB Process')
    while True:
        try:
            request = pipe.recv()
        except EOFError as err:
            logger.info('Breaking out of loop: %s', err)
            break

        try:
            req_id, method, *params = request
        except (TypeError, ValueError) as err:
            # TypeError: request is non iterable
            # ValueError: request is less than length-2
            pipe.send(err)

        try:
            if method == GET:
                key = params[0]
                logger.debug('GET: %s', key)

                try:
                    pipe.send([req_id, db.get(key)])
                except KeyError as err:
                    pipe.send([req_id, err])
            elif method == SET:
                key, value = params
                logger.debug('SET: %s -> %s', key, value)
                try:
                    pipe.send([req_id, db.set(key, value)])
                except KeyError as err:
                    pipe.send([req_id, err])
            elif method == EXISTS:
                key = params[0]
                logger.debug('EXISTS: %s', key)
                try:
                    pipe.send([req_id, db.exists(key)])
                except KeyError as err:
                    pipe.send([req_id, err])
            elif method == DELETE:
                key = params[0]
                logger.debug('DELETE: %s', key)
                try:
                    pipe.send([req_id, db.delete(key)])
                except KeyError as err:
                    pipe.send([req_id, err])
            else:
                logger.error("Got unknown method: %s: %s", method, params)
                pipe.send(Exception("Invalid request method: {0}".format(method)))
        except Exception as err:
            # Push the failure out to whatever process was trying to interact
            # with the database.
            pipe.send(err)
