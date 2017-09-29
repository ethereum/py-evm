from rlp import sedes

from evm.p2p.protocol import (
    Command,
    Protocol,
)


class Status(Command):
    _cmd_id = 0
    decode_strict = False
    structure = sedes.CountableList(sedes.List([sedes.binary, sedes.raw]))
    items_sedes = {
        b'protocolVersion': sedes.big_endian_int,
        b'networkId': sedes.big_endian_int,
        b'headTd': sedes.big_endian_int,
        b'headHash': sedes.binary,
        b'headNum': sedes.big_endian_int,
        b'genesisHash': sedes.binary,
        b'serveHeaders': None,
        b'serveChainSince': sedes.big_endian_int,
        b'serveStateSince': sedes.big_endian_int,
        b'txRelay': None,
        b'flowControl/BL': sedes.big_endian_int,
        b'flowControl/MRC': sedes.CountableList(
            sedes.List([sedes.big_endian_int, sedes.big_endian_int, sedes.big_endian_int])),
        b'flowControl/MRR': sedes.big_endian_int,
    }

    def decode_payload(self, rlp_data):
        decoded = super(Status, self).decode_payload(rlp_data)
        D = {}
        for key, value in decoded:
            item_sedes = self.items_sedes[key]
            if item_sedes is not None:
                D[key] = item_sedes.deserialize(value)
            else:
                D[key] = value
        return D

    def handle(self, proto, data):
        # TODO
        decoded = self.decode(data)
        proto.logger.debug("Got LES/Status msg: {}".format(decoded))


class LESProtocol(Protocol):
    name = b'les'
    version = 1
    _commands = [Status]
    # FIXME: Need to find out the correct value for this
    cmd_length = 21
