class BaseLibp2pError(Exception):
    pass


class HandshakeFailure(BaseLibp2pError):
    pass


class MessageIOFailure(BaseLibp2pError):
    pass


class ReadMessageFailure(MessageIOFailure):
    pass


class WriteMessageFailure(MessageIOFailure):
    pass


class InteractionFailure(BaseLibp2pError):
    pass


class ValidationError(BaseLibp2pError):
    pass


class RequestFailure(BaseLibp2pError):
    pass


class ResponseFailure(BaseLibp2pError):
    pass


class IrrelevantNetwork(ValidationError):
    pass
