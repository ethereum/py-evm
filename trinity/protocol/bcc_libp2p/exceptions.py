class BaseLibp2pError(Exception):
    pass


class HandshakeFailure(BaseLibp2pError):
    pass


class ReadMessageFailure(BaseLibp2pError):
    pass


class WriteMessageFailure(BaseLibp2pError):
    pass


class ValidationError(BaseLibp2pError):
    pass
