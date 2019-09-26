import factory

from p2p.handshake import DevP2PHandshakeParams
from p2p.p2p_proto import HelloPayload

from .keys import PublicKeyFactory


class HelloPayloadFactory(factory.Factory):
    class Meta:
        model = HelloPayload

    listen_port = 30303
    client_version_string = 'test'
    version = 5
    capabilities = ()
    remote_public_key = factory.LazyFunction(lambda: PublicKeyFactory().to_bytes())


class DevP2PHandshakeParamsFactory(factory.Factory):
    class Meta:
        model = DevP2PHandshakeParams

    listen_port = 30303
    client_version_string = 'test'
    version = 5
