class BaseLibp2pError(Exception):
    ...


class HandshakeFailure(BaseLibp2pError):
    ...


class MessageIOFailure(BaseLibp2pError):
    ...


class ReadMessageFailure(MessageIOFailure):
    ...


class WriteMessageFailure(MessageIOFailure):
    ...


class RequestFailure(BaseLibp2pError):
    ...


class PeerRespondedAnError(BaseLibp2pError):
    ...


class InvalidRequestSaidPeer(PeerRespondedAnError):
    ...


class ServerErrorSaidPeer(PeerRespondedAnError):
    ...


class IrrelevantNetwork(BaseLibp2pError):
    ...


class IShouldRespondAnError(BaseLibp2pError):
    ...


class InvalidRequest(IShouldRespondAnError):
    ...


class ServerError(IShouldRespondAnError):
    ...


class UnhandshakedPeer(BaseLibp2pError):
    ...
