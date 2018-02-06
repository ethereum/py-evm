import logging
import uuid

from evm.db.backends.base import (
    BaseDB,
)


GET = 0
SET = 1
EXISTS = 2
DELETE = 3


class PipeDB(BaseDB):
    pipe = None

    def __init__(self, pipe):
        self.pipe = pipe

    def get(self, key):
        req_id = uuid.uuid4()
        self.pipe.send([req_id, GET, key])

        resp_id, response = self.pipe.recv()
        if resp_id != req_id:
            raise ValueError('Request/Response id mismatch')

        if isinstance(response, Exception):
            raise response
        return response

    def set(self, key, value):
        req_id = uuid.uuid4()
        self.pipe.send([req_id, SET, key, value])

        resp_id, response = self.pipe.recv()
        if resp_id != req_id:
            raise ValueError('Request/Response id mismatch')

        if isinstance(response, Exception):
            raise response
        return response

    def exists(self, key):
        req_id = uuid.uuid4()
        self.pipe.send([req_id, EXISTS, key])

        resp_id, response = self.pipe.recv()
        if resp_id != req_id:
            raise ValueError('Request/Response id mismatch')

        if isinstance(response, Exception):
            raise response
        return response

    def delete(self, key):
        req_id = uuid.uuid4()
        self.connection.send([req_id, DELETE, key])

        resp_id, response = self.pipe.recv()
        if resp_id != req_id:
            raise ValueError('Request/Response id mismatch')

        if isinstance(response, Exception):
            raise response
        return response


def db_over_pipe(db, pipe):
    logger = logging.getLogger('trinity.main.db_process')

    logger.info('Starting DB Process')
    while True:
        try:
            request = pipe.recv()
        except EOFError as err:
            logger.info('Breaking out of loop: %s', err)
            break

        req_id, method, *params = request

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
            raise Exception('Invalid request method')
