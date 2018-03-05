import functools
import logging

from evm.utils.datatypes import Configurable


class Opcode(Configurable):
    mnemonic = None
    gas_cost = None

    def __init__(self):
        if self.mnemonic is None:
            raise TypeError("Opcode class {0} missing opcode mnemonic".format(type(self)))
        if self.gas_cost is None:
            raise TypeError("Opcode class {0} missing opcode gas_cost".format(type(self)))

    def __call__(self, computation):
        """
        Hook for performing the actual VM execution.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def logger(self):
        return logging.getLogger('evm.vm.logic.call.{0}'.format(self.mnemonic))

    @classmethod
    def as_opcode(cls, logic_fn, mnemonic, gas_cost):
        """
        Class factory method for turning vanilla functions into Opcode classes.
        """
        if gas_cost:
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
        else:
            wrapped_logic_fn = logic_fn

        props = {
            '__call__': staticmethod(wrapped_logic_fn),
            'mnemonic': mnemonic,
            'gas_cost': gas_cost,
        }
        opcode_cls = type("opcode:{0}".format(mnemonic), (cls,), props)
        return opcode_cls()

    def __copy__(self):
        return type(self)()

    def __deepcopy__(self, memo):
        return type(self)()


as_opcode = Opcode.as_opcode
