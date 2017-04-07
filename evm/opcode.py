import functools


class Opcode(object):
    value = None
    mnemonic = None
    gas_cost = None

    def __init__(self):
        if self.value is None:
            raise TypeError("Opcode class {0} missing opcode value".format(type(self)))
        if self.mnemonic is None:
            raise TypeError("Opcode class {0} missing opcode mnemonic".format(type(self)))
        if self.gas_cost is None:
            raise TypeError("Opcode class {0} missing opcode gas_cost".format(type(self)))

    def __call__(self, computation):
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    def as_opcode(cls, logic_fn, value, mnemonic, gas_cost):

        @functools.wraps(logic_fn)
        def wrapped_logic_fn(computation):
            """
            Wrapper functionf or the logic function which consumes the base
            opcode gas cost prior to execution.
            """
            computation.gas_meter.consume_gas(
                gas_cost,
                reason=mnemonic,
            )
            return logic_fn(computation)

        props = {
            '__call__': staticmethod(wrapped_logic_fn),
            'value': value,
            'mnemonic': mnemonic,
            'gas_cost': gas_cost,
        }
        opcode_cls = type(mnemonic, (cls,), props)
        return opcode_cls()


as_opcode = Opcode.as_opcode
