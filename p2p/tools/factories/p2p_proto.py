import factory

from p2p.handshake import DevP2PHandshakeParams


class DevP2PHandshakeParamsFactory(factory.Factory):
    class Meta:
        model = DevP2PHandshakeParams

    listen_port = 30303
    client_version_string = 'test'
    version = 5
