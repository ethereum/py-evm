import itertools

import rlp
from rlp import sedes

from eth_utils import to_dict

from evm.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_DIFFICULTY,
    ZERO_HASH32,
)
from evm.utils.hexadecimal import decode_hex
from evm.rlp.headers import (
    BlockHeader,
)
from evm.p2p.protocol import (
    Command,
    Protocol,
)


class Status(Command):
    _cmd_id = 0
    decode_strict = False
    # A list of (key, value) pairs is all a Status msg contains, but since the values can be of
    # any type, we need to use the raw sedes here and do the actual deserialization in
    # decode_payload().
    structure = sedes.CountableList(sedes.List([sedes.binary, sedes.raw]))
    # The sedes used for each key in the list above.
    items_sedes = {
        'protocolVersion': sedes.big_endian_int,
        'networkId': sedes.big_endian_int,
        'headTd': sedes.big_endian_int,
        'headHash': sedes.binary,
        'headNum': sedes.big_endian_int,
        'genesisHash': sedes.binary,
        'serveHeaders': None,
        'serveChainSince': sedes.big_endian_int,
        'serveStateSince': sedes.big_endian_int,
        'txRelay': None,
        'flowControl/BL': sedes.big_endian_int,
        'flowControl/MRC': sedes.CountableList(
            sedes.List([sedes.big_endian_int, sedes.big_endian_int, sedes.big_endian_int])),
        'flowControl/MRR': sedes.big_endian_int,
    }

    @to_dict
    def decode_payload(self, rlp_data):
        data = super(Status, self).decode_payload(rlp_data)
        # The LES/Status msg contains an arbitrary list of (key, value) pairs, where values can
        # have different types and unknown keys should be ignored for forward compatibility
        # reasons, so here we need an extra pass to deserialize each of the key/value pairs we
        # know about.
        for key, value in data:
            # The sedes.binary we use in .structure above will give us a bytes value here, but
            # using bytes as dictionary keys makes it impossible to use the dict() constructor
            # with keyword arguments, so we convert them to strings here.
            key = key.decode('ascii')
            if key not in self.items_sedes:
                continue
            item_sedes = self.items_sedes[key]
            if item_sedes is not None:
                yield key, item_sedes.deserialize(value)
            else:
                yield key, value

    def encode_payload(self, data):
        response = [
            (key, self.items_sedes[key].serialize(value))
            for key, value
            in sorted(data.items())
        ]
        return super(Status, self).encode_payload(response)

    def handle(self, proto, data):
        return self.decode(data)


class Announce(Command):
    _cmd_id = 1
    structure = [
        ('headHash', sedes.binary),
        ('headNumber', sedes.big_endian_int),
        ('headTd', sedes.big_endian_int),
        ('reorgDepth', sedes.big_endian_int),
        ('params', sedes.CountableList(sedes.List([sedes.binary, sedes.raw]))),
    ]
    # TODO: The params CountableList above may contain any of the values from the Status msg.
    # Need to extend this command to process that too.

    def handle(self, proto, data):
        decoded = self.decode(data)
        # FIXME: Should ask only for block headers we don't have yet.
        proto.send_get_block_headers(decoded['headNumber'])
        return decoded


class GetBlockHeadersQuery(rlp.Serializable):
    fields = [
        # TODO: It should be possible to specify the block either by its number or hash, but
        # for now only the number is supported.
        ('block', sedes.big_endian_int),
        ('maxHeaders', sedes.big_endian_int),
        ('skip', sedes.big_endian_int),
        ('reverse', sedes.big_endian_int),
    ]


class GetBlockHeaders(Command):
    _cmd_id = 2
    structure = [
        ('request_id', sedes.big_endian_int),
        ('query', GetBlockHeadersQuery),
    ]


class BlockHeaders(Command):
    _cmd_id = 3
    structure = [
        ('request_id', sedes.big_endian_int),
        ('buffer_value', sedes.big_endian_int),
        ('headers', sedes.CountableList(BlockHeader)),
    ]

    def handle(self, proto, data):
        decoded = self.decode(data)
        last_header_seen = decoded['headers'][0].block_number
        proto.logger.debug("Last block header received: {}".format(last_header_seen))
        return decoded


class LESProtocol(Protocol):
    name = b'les'
    version = 1
    _commands = [Status, Announce, BlockHeaders]
    _req_id = itertools.count()
    # By default, whenever we send a GetBlockHeaders we'll expect max_headers in response.
    # FIXME: Should be a config value somewhere, maybe?
    max_headers = 10
    handshake_msg_type = Status
    cmd_length = 15

    def send_handshake(self):
        resp = {
            'protocolVersion': self.version,
            # FIXME: Need a Chain instance to get the values below from.
            'networkId': 3,
            'headTd': GENESIS_DIFFICULTY,
            'headHash': ZERO_HASH32,
            'headNum': GENESIS_BLOCK_NUMBER,
            'genesisHash': decode_hex(
                '0x41941023680923e0fe4d74a34bdac8141f2540e3ae90623718e47d66d1ca4a2d'),
        }
        cmd = Status(self.cmd_id_offset)
        self.send(*cmd.encode(resp))
        self.logger.debug("Sending LES/Status msg: {}".format(resp))

    def process_handshake(self, decoded_msg):
        # TODO: Possibly disconnect if any of
        # 1. remote doesn't serve headers
        # 2. genesis hash does not match
        pass

    @property
    def next_req_id(self):
        return next(self._req_id)

    def send_get_block_headers(self, block_number, reverse=True, max_headers=max_headers):
        """Send a GetBlockHeaders msg to the remote.

        This requests that the remote send us up to max_headers, starting from block_number if
        reverse is False or ending at block_number if reverse is True.
        """
        cmd = GetBlockHeaders(self.cmd_id_offset)
        # Number of block headers to skip between each item (i.e. step in python APIs).
        skip = 0
        data = {
            'request_id': self.next_req_id,
            'query': GetBlockHeadersQuery(block_number, max_headers, skip, reverse),
        }
        header, body = cmd.encode(data)
        return self.send(header, body)
