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
        self.mp_pipe.send([GET, key])
        response = self.mp_pipe.recv()
        if isinstance(response, Exception):
            raise response
        return response

    def set(self, key, value):
        self.mp_pipe.send([SET, key, value])
        response = self.mp_pipe.recv()
        if isinstance(response, Exception):
            raise response

    def exists(self, key):
        self.mp_pipe.send([EXISTS, key])
        response = self.mp_pipe.recv()
        if isinstance(response, Exception):
            raise response
        return response

    def delete(self, key):
        self.mp_connection.send([DELETE, key])
        response = self.mp_pipe.recv()
        if isinstance(response, Exception):
            raise response
        return response
