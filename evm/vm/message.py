import logging

from evm.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from evm.validation import (
    validate_canonical_address,
    validate_is_bytes,
    validate_is_integer,
    validate_gte,
    validate_uint256,
    validate_is_boolean,
    validate_access_list,
    validate_sig_hash,
)


class Message(object):
    """
    A message for VM computation.
    """
    origin = None
    to = None
    sender = None
    value = None
    data = None
    gas = None
    gas_price = None
    access_list = None

    depth = None

    code = None
    _code_address = None

    create_address = None

    should_transfer_value = None
    is_static = None

    logger = logging.getLogger('evm.vm.message.Message')

    def __init__(self,
                 gas,
                 gas_price,
                 to,
                 sender,
                 value,
                 data,
                 code,
                 origin=None,
                 access_list=None,
                 depth=0,
                 create_address=None,
                 code_address=None,
                 should_transfer_value=True,
                 is_static=False):
        validate_uint256(gas, title="Message.gas")
        self.gas = gas

        validate_uint256(gas_price, title="Message.gas_price")
        self.gas_price = gas_price

        if to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(to, title="Message.to")
        self.to = to

        validate_canonical_address(sender, title="Message.sender")
        self.sender = sender

        validate_uint256(value, title="Message.value")
        self.value = value

        validate_is_bytes(data, title="Message.data")
        self.data = data

        if origin is not None:
            validate_canonical_address(origin, title="Message.origin")
        self.origin = origin

        validate_is_integer(depth, title="Message.depth")
        validate_gte(depth, minimum=0, title="Message.depth")
        self.depth = depth

        validate_is_bytes(code, title="Message.code")
        self.code = code

        if create_address is not None:
            validate_canonical_address(create_address, title="Message.storage_address")
        self.storage_address = create_address

        if code_address is not None:
            validate_canonical_address(code_address, title="Message.code_address")
        self.code_address = code_address

        validate_is_boolean(should_transfer_value, title="Message.should_transfer_value")
        self.should_transfer_value = should_transfer_value

        validate_is_boolean(is_static, title="Message.is_static")
        self.is_static = is_static

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
        return self.to == CREATE_CONTRACT_ADDRESS


class ShardingMessage(Message):

    is_create = False

    def __init__(self,
                 gas,
                 gas_price,
                 to,
                 sig_hash,
                 sender,
                 value,
                 data,
                 code,
                 origin=None,
                 access_list=None,
                 depth=0,
                 is_create=False,
                 code_address=None,
                 should_transfer_value=True,
                 is_static=False):
        super(ShardingMessage, self).__init__(
            gas=gas,
            gas_price=gas_price,
            to=to,
            sender=sender,
            value=value,
            data=data,
            code=code,
            origin=origin,
            depth=depth,
            create_address=to,
            code_address=code_address,
            should_transfer_value=should_transfer_value,
            is_static=is_static,
        )

        validate_is_boolean(is_create, title="Message.is_create")
        self.is_create = is_create

        validate_sig_hash(sig_hash, title="Message.sig_hash")
        self.sig_hash = sig_hash

        if access_list is not None:
            validate_access_list(access_list)
        self.access_list = access_list

    def prepare_child_message(self,
                              gas,
                              to,
                              value,
                              data,
                              code,
                              **kwargs):
        kwargs.setdefault('sender', self.msg.storage_address)

        child_message = ShardingMessage(
            gas=gas,
            gas_price=self.msg.gas_price,
            origin=self.msg.origin,
            sig_hash=self.msg.sig_hash,
            to=to,
            value=value,
            data=data,
            code=code,
            depth=self.msg.depth + 1,
            **kwargs
        )
        return child_message
