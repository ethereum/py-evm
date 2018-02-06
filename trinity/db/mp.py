import uuid

from evm.db.backends.base import (
    BaseDB,
)


GET = 0
SET = 1
EXISTS = 2
DELETE = 3


class MPDB(BaseDB):
    mp_pipe = None

    def __init__(self, mp_pipe):
        self.mp_pipe = mp_pipe

    def get(self, key):
        req_id = uuid.uuid4()
        self.mp_pipe.send([req_id, GET, key])

        resp_id, response = self.mp_pipe.recv()
        if resp_id != req_id:
            raise ValueError('Request/Response id mismatch')

        if isinstance(response, Exception):
            raise response
        return response

    def set(self, key, value):
        req_id = uuid.uuid4()
        self.mp_pipe.send([req_id, SET, key, value])

        resp_id, response = self.mp_pipe.recv()
        if resp_id != req_id:
            raise ValueError('Request/Response id mismatch')

        if isinstance(response, Exception):
            raise response
        return response

    def exists(self, key):
        req_id = uuid.uuid4()
        self.mp_pipe.send([req_id, EXISTS, key])

        resp_id, response = self.mp_pipe.recv()
        if resp_id != req_id:
            raise ValueError('Request/Response id mismatch')

        if isinstance(response, Exception):
            raise response
        return response

    def delete(self, key):
        req_id = uuid.uuid4()
        self.mp_connection.send([req_id, DELETE, key])

        resp_id, response = self.mp_pipe.recv()
        if resp_id != req_id:
            raise ValueError('Request/Response id mismatch')

        if isinstance(response, Exception):
            raise response
        return response
