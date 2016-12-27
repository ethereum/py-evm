import collections
import io


from evm import opcodes
from evm import operations


def lazy_dict():
    return collections.defaultdict(lazy_dict)


class EVM(object):
    storage = {}

    def __init__(self):
        self.storage = lazy_dict()

    def set_storage(self, account, slot, value):
        self.storage[account]['storage'][slot] = value

    def get_storage(self, account, slot):
        return self.storage[account]['storage'][slot]

    def set_balance(self, account, balance):
        self.storage[account]['balance'] = balance

    def get_balance(self, account):
        return self.storage[account]['balance']

    def set_nonce(self, account, nonce):
        self.storage[account]['nonce'] = nonce

    def get_nonce(self, account):
        return self.storage[account]['nonce']

    def set_code(self, account, code):
        self.storage[account]['code'] = code

    def get_code(self, account):
        return self.storage[account]['code']


class LocalState(object):
    memory = None
    stack = None
    gas = None
    gas_price = None

    origin = None
    account = None
    sender = None
    value = None
    data = None

    def __init__(self, origin, account, sender, value, data, gas, gas_price):
        self.memory = []
        self.stack = []

        self.gas = gas
        self.gas_price = gas_price

        self.origin = origin
        self.account = account
        self.sender = sender
        self.value = value

        self.data = data


def execute_vm(evm, origin, account, sender, value, data, gas, gas_price):
    local_state = LocalState(
        origin=origin,
        account=account,
        sender=sender,
        value=value,
        data=data,
        gas=gas,
        gas_price=gas_price,
    )

    if data:
        raise NotImplementedError("Not Implemented")

    code = evm.get_code(account)
    code_stream = io.BytesIO(code)

    while True:
        opcode_raw = code_stream.read1(1)
        if opcode_raw == b'':
            break

        opcode = ord(opcode_raw)

        if opcode == opcodes.PUSH1:
            operations.push_XX(evm, local_state, code_stream, 1)
        elif opcode == opcodes.PUSH32:
            operations.push_XX(evm, local_state, code_stream, 32)
        elif opcode == opcodes.ADD:
            operations.add(evm, local_state, code_stream)
        elif opcode == opcodes.SSTORE:
            operations.sstore(evm, local_state, code_stream)
        else:
            raise NotImplementedError("Not Implemented")
    return evm
