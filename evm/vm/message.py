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
)


class Message(object):
    """
    A message for VM computation.
    """
    to = None
    sender = None
    value = None
    data = None
    gas = None
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
                 to,
                 sender,
                 value,
                 data,
                 code,
                 access_list=None,
                 depth=0,
                 create_address=None,
                 code_address=None,
                 should_transfer_value=True,
                 is_static=False):
        validate_uint256(gas, title="Message.gas")
        self.gas = gas

        if to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(to, title="Message.to")
        self.to = to

        validate_canonical_address(sender, title="Message.sender")
        self.sender = sender

        validate_uint256(value, title="Message.value")
        self.value = value

        validate_is_bytes(data, title="Message.data")
        self.data = data

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
                 to,
                 sender,
                 value,
                 data,
                 code,
                 access_list=None,
                 depth=0,
                 is_create=False,
                 code_address=None,
                 should_transfer_value=True,
                 is_static=False):
        super(ShardingMessage, self).__init__(
            gas=gas,
            to=to,
            sender=sender,
            value=value,
            data=data,
            code=code,
            depth=depth,
            create_address=to,
            code_address=code_address,
            should_transfer_value=should_transfer_value,
            is_static=is_static,
        )

        validate_is_boolean(is_create, title="Message.is_create")
        self.is_create = is_create

        if access_list is not None:
            validate_access_list(access_list)
        self.access_list = access_list
