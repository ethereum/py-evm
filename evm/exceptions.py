class EVMError(Exception):
    pass


class EmptyStream(EVMError):
    pass


class OutOfGas(EVMError):
    pass
