import logging

from evm.validation import (
    validate_canonical_address,
    validate_is_bytes,
    validate_is_integer,
    validate_gte,
    validate_uint256,
)


class Message(object):
    """
    A message for EVM computation.
    """
    origin = None
    to = None
    sender = None
    value = None
    data = None
    gas = None
    gas_price = None

    depth = None

    _code_address = None
    create_address = None

    logger = logging.getLogger('evm.vm.message.Message')

    def __init__(self,
                 gas,
                 gas_price,
                 to,
                 sender,
                 value,
                 data,
                 origin=None,
                 depth=0,
                 code_address=None,
                 create_address=None):
        validate_uint256(gas)
        self.gas = gas

        validate_uint256(gas_price)
        self.gas_price = gas_price

        validate_canonical_address(to)
        self.to = to

        validate_canonical_address(sender)
        self.sender = sender

        validate_uint256(value)
        self.value = value

        validate_is_bytes(data)
        self.data = data

        if origin is not None:
            validate_canonical_address(origin)
        self.origin = origin

        validate_is_integer(depth)
        validate_gte(depth, minimum=0)
        self.depth = depth

        if code_address is not None:
            validate_canonical_address(code_address)
        self.code_address = code_address

        if create_address is not None:
            validate_canonical_address(create_address)
        self.storage_address = create_address

    @property
    def is_origin(self):
        return self.sender == self.origin

    @property
    def origin(self):
        if self._origin is not None:
            return self._origin
        else:
            return self.sender

    @origin.setter
    def origin(self, value):
        self._origin = value

    @property
    def code_address(self):
        if self._code_address is not None:
            return self._code_address
        else:
            return self.to

    @code_address.setter
    def code_address(self, value):
        self._code_address = value

    @property
    def storage_address(self):
        if self._storage_address is not None:
            return self._storage_address
        else:
            return self.to

    @storage_address.setter
    def storage_address(self, value):
        self._storage_address = value

    @property
    def is_create(self):
        return self._storage_address is not None
