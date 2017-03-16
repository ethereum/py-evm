class EVMError(Exception):
    pass


class EmptyStream(EVMError):
    pass


class InsufficientStack(EVMError):
    pass


class FullStack(EVMError):
    pass


class InvalidJumpDestination(EVMError):
    pass


class InvalidInstruction(EVMError):
    pass


class OutOfGas(EVMError):
    pass
