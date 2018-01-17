from rlp import sedes


class HashOrNumber:

    def serialize(self, obj):
        if isinstance(obj, int):
            return sedes.big_endian_int.serialize(obj)
        return sedes.binary.serialize(obj)

    def deserialize(self, serial):
        if len(serial) == 32:
            return sedes.binary.deserialize(serial)
        return sedes.big_endian_int.deserialize(serial)
