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


class RequestFailure(BaseLibp2pError):
    pass


class PeerRespondedAnError(BaseLibp2pError):
    pass


class IrrelevantNetwork(BaseLibp2pError):
    pass


class IShouldRespondAnError(BaseLibp2pError):
    pass


class InvalidRequest(IShouldRespondAnError):
    pass


class ServerError(IShouldRespondAnError):
    pass


class UnhandshakedPeer(BaseLibp2pError):
    pass
