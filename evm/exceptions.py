class EVMError(Exception):
    pass


class EmptyStream(EVMError):
    pass


class InsufficientStack(EVMError):
    pass


class FullStack(EVMError):
    pass


class OutOfGas(EVMError):
    pass
