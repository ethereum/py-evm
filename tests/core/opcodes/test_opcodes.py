import pytest

from eth_utils import (
    decode_hex,
    encode_hex,
    to_canonical_address,
    int_to_big_endian,
)

from eth import (
    constants
)
from eth.utils.padding import (
    pad32
)
from eth.vm import (
    opcode_values
)
from eth.vm.forks import (
    ConstantinopleVM,
    ByzantiumVM,
    SpuriousDragonVM,
    TangerineWhistleVM,
    HomesteadVM,
    FrontierVM,
)

from eth.vm.message import (
    Message,
)


NORMALIZED_ADDRESS_A = "0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"
NORMALIZED_ADDRESS_B = "0xcd1722f3947def4cf144679da39c4c32bdc35681"
CANONICAL_ADDRESS_A = to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6")
CANONICAL_ADDRESS_B = to_canonical_address("0xcd1722f3947def4cf144679da39c4c32bdc35681")


def prepare_computation(vm_class):

    message = Message(
        to=CANONICAL_ADDRESS_A,
        sender=CANONICAL_ADDRESS_B,
        value=100,
        data=b'',
        code=b'',
        gas=800,
    )

    tx_context = vm_class._state_class.transaction_context_class(
        gas_price=1,
        origin=CANONICAL_ADDRESS_B,
    )

    computation = vm_class._state_class.computation_class(
        state=None,
        message=message,
        transaction_context=tx_context,
    )
    return computation


@pytest.mark.parametrize(
    'vm_class, val1, val2, expected',
    (
        (ByzantiumVM, 2, 4, 6,),
        (SpuriousDragonVM, 2, 4, 6,),
        (TangerineWhistleVM, 2, 4, 6,),
        (HomesteadVM, 2, 4, 6,),
        (FrontierVM, 2, 4, 6,),
    )
)
def test_add(vm_class, val1, val2, expected):
    computation = prepare_computation(vm_class)
    computation.stack_push(val1)
    computation.stack_push(val2)
    computation.opcodes[opcode_values.ADD](computation)

    result = computation.stack_pop(type_hint=constants.UINT256)

    assert result == expected


@pytest.mark.parametrize(
    'vm_class, val1, val2, expected',
    (
        (ByzantiumVM, 2, 2, 4,),
        (SpuriousDragonVM, 2, 2, 4,),
        (TangerineWhistleVM, 2, 2, 4,),
        (HomesteadVM, 2, 2, 4,),
        (FrontierVM, 2, 2, 4,),
    )
)
def test_mul(vm_class, val1, val2, expected):
    computation = prepare_computation(vm_class)
    computation.stack_push(val1)
    computation.stack_push(val2)
    computation.opcodes[opcode_values.MUL](computation)

    result = computation.stack_pop(type_hint=constants.UINT256)

    assert result == expected


@pytest.mark.parametrize(
    # Testcases from https://github.com/ethereum/EIPs/blob/master/EIPS/eip-145.md#shl-shift-left
    'vm_class, val1, val2, expected',
    (
        (
            ConstantinopleVM,
            '0x0000000000000000000000000000000000000000000000000000000000000001',
            '0x00',
            '0x0000000000000000000000000000000000000000000000000000000000000001',
        ),
        (
            ConstantinopleVM,
            '0x0000000000000000000000000000000000000000000000000000000000000001',
            '0x01',
            '0x0000000000000000000000000000000000000000000000000000000000000002',
        ),
        (
            ConstantinopleVM,
            '0x0000000000000000000000000000000000000000000000000000000000000001',
            '0xff',
            '0x8000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0x0000000000000000000000000000000000000000000000000000000000000001',
            '0x0100',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0x0000000000000000000000000000000000000000000000000000000000000001',
            '0x0101',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0x00',
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        ),
        (
            ConstantinopleVM,
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0x01',
            '0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe',
        ),
        (
            ConstantinopleVM,
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0xff',
            '0x8000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0x0100',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0x0000000000000000000000000000000000000000000000000000000000000000',
            '0x01',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0x01',
            '0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe',
        ),
    )
)
def test_shl(vm_class, val1, val2, expected):
    computation = prepare_computation(vm_class)
    computation.stack_push(decode_hex(val1))
    computation.stack_push(decode_hex(val2))
    computation.opcodes[opcode_values.SHL](computation)

    result = computation.stack_pop(type_hint=constants.UINT256)

    assert encode_hex(pad32(int_to_big_endian(result))) == expected


@pytest.mark.parametrize(
    # Cases: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-145.md#shr-logical-shift-right
    'vm_class, val1, val2, expected',
    (
        (
            ConstantinopleVM,
            '0x0000000000000000000000000000000000000000000000000000000000000001',
            '0x00',
            '0x0000000000000000000000000000000000000000000000000000000000000001',
        ),
        (
            ConstantinopleVM,
            '0x0000000000000000000000000000000000000000000000000000000000000001',
            '0x01',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0x8000000000000000000000000000000000000000000000000000000000000000',
            '0x01',
            '0x4000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0x8000000000000000000000000000000000000000000000000000000000000000',
            '0xff',
            '0x0000000000000000000000000000000000000000000000000000000000000001',
        ),
        (
            ConstantinopleVM,
            '0x8000000000000000000000000000000000000000000000000000000000000000',
            '0x0100',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0x8000000000000000000000000000000000000000000000000000000000000000',
            '0x0101',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0x00',
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        ),
        (
            ConstantinopleVM,
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0x01',
            '0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        ),
        (
            ConstantinopleVM,
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0xff',
            '0x0000000000000000000000000000000000000000000000000000000000000001',
        ),
        (
            ConstantinopleVM,
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0x0100',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0x0000000000000000000000000000000000000000000000000000000000000000',
            '0x01',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
    )
)
def test_shr(vm_class, val1, val2, expected):
    computation = prepare_computation(vm_class)
    computation.stack_push(decode_hex(val1))
    computation.stack_push(decode_hex(val2))
    computation.opcodes[opcode_values.SHR](computation)

    result = computation.stack_pop(type_hint=constants.UINT256)
    assert encode_hex(pad32(int_to_big_endian(result))) == expected
