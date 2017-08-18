import asyncio

import rlp


class BaseProtocol(asyncio.Protocol):
    protocol_id = 0
    name = ''
    version = 0
    max_cmd_id = 0  # reserved cmd space

    def __init__(self):
        self._setup()

    def _setup(self):

        def create_methods(klass):
            instance = klass()

            def receive(packet):
                "decode rlp, create dict, call receive"
                assert isinstance(packet, Packet)
                instance.receive(proto=self, data=klass.decode_payload(packet.payload))

            def create(*args, **kargs):
                "get data, rlp encode, return packet"
                res = instance.create(self, *args, **kargs)
                payload = klass.encode_payload(res)
                return Packet(self.protocol_id, klass.cmd_id, payload=payload)

            def send(*args, **kargs):
                "create and send packet"
                packet = create(*args, **kargs)
                self.send_packet(packet)

            return receive, create, send, instance.receive_callbacks

        for klass in self._commands:
            receive, create, send, receive_callbacks = create_methods(klass)
            setattr(self, '_receive_' + klass.__name__, receive)
            setattr(self, 'receive_' + klass.__name__ + '_callbacks', receive_callbacks)
            setattr(self, 'create_' + klass.__name__, create)
            setattr(self, 'send_' + klass.__name__, send)

        self.cmd_by_id = dict((klass.cmd_id, klass.__name__) for klass in self._commands)

    def receive_packet(self, packet):
        cmd_name = self.cmd_by_id[packet.cmd_id]
        handler = getattr(self, '_receive_' + cmd_name)
        handler(packet)

    def send_packet(self, packet):
        self.peer.send_packet(packet)


class Command():
    cmd_id = 0
    structure = []

    def create(self, proto, *args, **kargs):
        "optionally implement create"
        assert isinstance(proto, BaseProtocol)
        assert not (kargs and isinstance(self.structure, rlp.sedes.CountableList))
        return kargs or args

    def receive(self, proto, data):
        "optionally implement receive"
        for cb in self.receive_callbacks:
            if isinstance(self.structure, rlp.sedes.CountableList):
                cb(proto, data)
            else:
                cb(proto, **data)

    def __init__(self):
        assert isinstance(self.structure, (list, rlp.sedes.CountableList))
        self.receive_callbacks = []

    @classmethod
    def encode_payload(cls, data):
        if isinstance(data, dict):  # convert dict to ordered list
            assert isinstance(cls.structure, list)
            data = [data[x[0]] for x in cls.structure]
        if isinstance(cls.structure, rlp.sedes.CountableList):
            return rlp.encode(data, cls.structure)
        else:
            assert len(data) == len(cls.structure)
            return rlp.encode(data, sedes=rlp.sedes.List([x[1] for x in cls.structure]))

    @classmethod
    def decode_payload(cls, rlp_data):
        if isinstance(cls.structure, rlp.sedes.CountableList):
            decoder = cls.structure
        else:
            decoder = rlp.sedes.List([x[1] for x in cls.structure])
        try:
            data = rlp.decode(rlp_data, sedes=decoder)
        except (AssertionError, rlp.RLPException, TypeError) as e:
            print(repr(rlp.decode(rlp_data)))
            raise e
        if isinstance(cls.structure, rlp.sedes.CountableList):
            return data
        else:  # convert to dict
            return dict((cls.structure[i][0], v) for i, v in enumerate(data))


class Packet(object):

    """
    Packets are emitted and received by subprotocols
    """

    def __init__(self, protocol_id=0, cmd_id=0, payload=b'', prioritize=False):
        self.protocol_id = protocol_id
        self.cmd_id = cmd_id
        self.payload = payload
        self.prioritize = prioritize

    def __repr__(self):
        return 'Packet(%r)' % dict(protocol_id=self.protocol_id,
                                   cmd_id=self.cmd_id,
                                   payload_len=len(self.payload),
                                   prioritize=self.prioritize)

    def __eq__(self, other):
        s = dict(self.__dict__)
        s.pop('prioritize')
        o = dict(other.__dict__)
        o.pop('prioritize')
        return s == o

    def __len__(self):
        return len(self.payload)
