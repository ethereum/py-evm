import rlp

from evm.p2p.protocol import (
    BaseProtocol,
    Command,
    Packet,
)


class P2PProtocol(BaseProtocol):

    """
    DEV P2P Wire Protocol
    https://github.com/ethereum/wiki/wiki/%C3%90%CE%9EVp2p-Wire-Protocol
    """
    protocol_id = 0
    name = b'p2p'
    version = 4
    max_cmd_id = 15

    def __init__(self, peer, service):
        # required by P2PProtocol
        self.config = peer.config
        assert hasattr(peer, 'capabilities')
        assert callable(peer.stop)
        assert callable(peer.receive_hello)
        super(P2PProtocol, self).__init__(peer, service)

    @classmethod
    def get_hello_packet(cls, peer):
        "special: we need this packet before the protocol can be initalized"
        res = dict(version=cls.version,
                   client_version_string=peer.config['client_version_string'],
                   capabilities=peer.capabilities,
                   listen_port=peer.config['p2p']['listen_port'],
                   remote_pubkey=peer.config['node']['id'])
        payload = cls.hello.encode_payload(res)
        return Packet(cls.protocol_id, cls.hello.cmd_id, payload=payload)


class ping(Command):
    cmd_id = 2

    def receive(self, proto, data):
        proto.send_pong()


class pong(Command):
    cmd_id = 3


class hello(Command):
    cmd_id = 0
    structure = [
        ('version', rlp.sedes.big_endian_int),
        ('client_version_string', rlp.sedes.binary),
        ('capabilities', rlp.sedes.CountableList(
            rlp.sedes.List([rlp.sedes.binary, rlp.sedes.big_endian_int]))),
        ('listen_port', rlp.sedes.big_endian_int),
        ('remote_pubkey', rlp.sedes.binary)
    ]
    # don't throw for additional list elements as
    # mandated by EIP-8.
    decode_strict = False

    def create(self, proto):
        return dict(version=proto.version,
                    client_version_string=proto.config['client_version_string'],
                    capabilities=proto.peer.capabilities,
                    listen_port=proto.config['p2p']['listen_port'],
                    remote_pubkey=proto.config['node']['id'],
                    )

    def receive(self, proto, data):
        reasons = proto.disconnect.reason
        if data['remote_pubkey'] == proto.config['node']['id']:
            return proto.send_disconnect(reason=reasons.connected_to_self)

        proto.peer.receive_hello(proto, **data)
        # super(hello, self).receive(proto, data)
        Command.receive(self, proto, data)


class disconnect(Command):
    cmd_id = 1
    structure = [('reason', rlp.sedes.big_endian_int)]

    class reason(object):
        disconnect_requested = 0
        tcp_sub_system_error = 1
        bad_protocol = 2         # e.g. a malformed message, bad RLP, incorrect magic number
        useless_peer = 3
        too_many_peers = 4
        already_connected = 5
        incompatibel_p2p_version = 6
        null_node_identity_received = 7
        client_quitting = 8
        unexpected_identity = 9  # i.e. a different identity to a previous connection or
        #                          what a trusted peer told us
        connected_to_self = 10
        timeout = 11             # i.e. nothing received since sending last ping
        subprotocol_error = 12
        other = 16               # Some other reason specific to a subprotocol

    def reason_name(self, _id):
        d = dict((_id, name) for name, _id in self.reason.__dict__.items())
        return d.get(_id, 'unknown (id:{})'.format(_id))

    def create(self, proto, reason=reason.client_quitting):
        assert self.reason_name(reason)
        proto.peer.report_error('sending disconnect %s' % self.reason_name(reason))
        # Defer disconnect until message is sent out.
        # gevent.spawn_later(0.5, proto.peer.stop)
        return dict(reason=reason)

    def receive(self, proto, data):
        proto.peer.report_error('disconnected %s' % self.reason_name(data['reason']))
        proto.peer.stop()
