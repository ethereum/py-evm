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
from eth.db.atomic import (
    AtomicDB
)
from eth.db.chain import (
    ChainDB
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth._utils.padding import (
    pad32
)
from eth.vm import (
    opcode_values
)
from eth.vm.chain_context import ChainContext
from eth.vm.forks import (
    IstanbulVM,
    PetersburgVM,
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
ADDRESS_WITH_CODE = ("0xddd722f3947def4cf144679da39c4c32bdc35681", b'pseudocode')
EMPTY_ADDRESS_IN_STATE = NORMALIZED_ADDRESS_A
ADDRESS_NOT_IN_STATE = NORMALIZED_ADDRESS_B
ADDRESS_WITH_JUST_BALANCE = "0x0000000000000000000000000000000000000001"
CANONICAL_ADDRESS_A = to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6")
CANONICAL_ADDRESS_B = to_canonical_address("0xcd1722f3947def4cf144679da39c4c32bdc35681")
GENESIS_HEADER = BlockHeader(
    difficulty=constants.GENESIS_DIFFICULTY,
    block_number=constants.GENESIS_BLOCK_NUMBER,
    gas_limit=constants.GENESIS_GAS_LIMIT,
)


def setup_computation(vm_class, create_address, code, chain_id=None, gas=1000000):
    if chain_id is None:
        chain_id = 42

    message = Message(
        to=CANONICAL_ADDRESS_A,
        sender=CANONICAL_ADDRESS_B,
        create_address=create_address,
        value=0,
        data=b'',
        code=code,
        gas=gas,
    )

    chain_context = ChainContext(chain_id)

    tx_context = vm_class._state_class.transaction_context_class(
        gas_price=1,
        origin=CANONICAL_ADDRESS_B,
    )

    vm = vm_class(GENESIS_HEADER, ChainDB(AtomicDB()), chain_context)

    computation = vm_class._state_class.computation_class(
        state=vm.state,
        message=message,
        transaction_context=tx_context,
    )

    return computation


def prepare_general_computation(vm_class, create_address=None, code=b'', chain_id=None):

    computation = setup_computation(vm_class, create_address, code, chain_id)

    computation.state.touch_account(decode_hex(EMPTY_ADDRESS_IN_STATE))
    computation.state.set_code(decode_hex(ADDRESS_WITH_CODE[0]), ADDRESS_WITH_CODE[1])

    computation.state.set_balance(decode_hex(ADDRESS_WITH_JUST_BALANCE), 1)

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
    computation = prepare_general_computation(vm_class)
    computation.stack_push_int(val1)
    computation.stack_push_int(val2)
    computation.opcodes[opcode_values.ADD](computation)

    result = computation.stack_pop1_int()

    assert result == expected


@pytest.mark.parametrize(
    'opcode_value, expected',
    (
        (opcode_values.COINBASE, b'\0' * 20),
        # (opcode_values.TIMESTAMP, 1556826898),
        (opcode_values.NUMBER, 0),
        (opcode_values.DIFFICULTY, 17179869184),
        (opcode_values.GASLIMIT, 5000),
    )
)
def test_nullary_opcodes(VM, opcode_value, expected):
    computation = prepare_general_computation(VM)
    computation.opcodes[opcode_value](computation)

    result = computation.stack_pop1_any()

    assert result == expected


@pytest.mark.parametrize(
    'val1, expected',
    (
        (0, b''),
        (1, b''),
        (255, b''),
        (256, b''),
    )
)
def test_blockhash(VM, val1, expected):
    computation = prepare_general_computation(VM)
    computation.stack_push_int(val1)
    computation.opcodes[opcode_values.BLOCKHASH](computation)

    result = computation.stack_pop1_any()

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
    computation = prepare_general_computation(vm_class)
    computation.stack_push_int(val1)
    computation.stack_push_int(val2)
    computation.opcodes[opcode_values.MUL](computation)

    result = computation.stack_pop1_int()

    assert result == expected


@pytest.mark.parametrize(
    'vm_class, base, exponent, expected',
    (
        (ByzantiumVM, 0, 1, 0,),
        (ByzantiumVM, 0, 0, 1,),
        (SpuriousDragonVM, 0, 1, 0,),
        (SpuriousDragonVM, 0, 0, 1,),
        (TangerineWhistleVM, 0, 1, 0,),
        (TangerineWhistleVM, 0, 0, 1,),
        (HomesteadVM, 0, 1, 0,),
        (HomesteadVM, 0, 0, 1,),
        (FrontierVM, 0, 1, 0,),
        (FrontierVM, 0, 0, 1,),
    )
)
def test_exp(vm_class, base, exponent, expected):
    computation = prepare_general_computation(vm_class)
    computation.stack_push_int(exponent)
    computation.stack_push_int(base)
    computation.opcodes[opcode_values.EXP](computation)

    result = computation.stack_pop1_int()

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
    computation = prepare_general_computation(vm_class)
    computation.stack_push_bytes(decode_hex(val1))
    computation.stack_push_bytes(decode_hex(val2))
    computation.opcodes[opcode_values.SHL](computation)

    result = computation.stack_pop1_int()

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
    computation = prepare_general_computation(vm_class)
    computation.stack_push_bytes(decode_hex(val1))
    computation.stack_push_bytes(decode_hex(val2))
    computation.opcodes[opcode_values.SHR](computation)

    result = computation.stack_pop1_int()
    assert encode_hex(pad32(int_to_big_endian(result))) == expected


@pytest.mark.parametrize(
    # EIP: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-145.md#sar-arithmetic-shift-right
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
            '0xc000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0x8000000000000000000000000000000000000000000000000000000000000000',
            '0xff',
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        ),
        (
            ConstantinopleVM,
            '0x8000000000000000000000000000000000000000000000000000000000000000',
            '0x0100',
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        ),
        (
            ConstantinopleVM,
            '0x8000000000000000000000000000000000000000000000000000000000000000',
            '0x0101',
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
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
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        ),
        (
            ConstantinopleVM,
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0xff',
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        ),
        (
            ConstantinopleVM,
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0x0100',
            '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        ),
        (
            ConstantinopleVM,
            '0x0000000000000000000000000000000000000000000000000000000000000000',
            '0x01',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),

        (
            ConstantinopleVM,
            '0x4000000000000000000000000000000000000000000000000000000000000000',
            '0xfe',
            '0x0000000000000000000000000000000000000000000000000000000000000001',
        ),
        (
            ConstantinopleVM,
            '0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0xf8',
            '0x000000000000000000000000000000000000000000000000000000000000007f',
        ),
        (
            ConstantinopleVM,
            '0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0xfe',
            '0x0000000000000000000000000000000000000000000000000000000000000001',
        ),
        (
            ConstantinopleVM,
            '0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0xff',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            '0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            '0x0100',
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
    )
)
def test_sar(vm_class, val1, val2, expected):
    computation = prepare_general_computation(vm_class)
    computation.stack_push_bytes(decode_hex(val1))
    computation.stack_push_bytes(decode_hex(val2))
    computation.opcodes[opcode_values.SAR](computation)

    result = computation.stack_pop1_int()
    assert encode_hex(pad32(int_to_big_endian(result))) == expected


@pytest.mark.parametrize(
    'vm_class, address, expected',
    (
        (
            ConstantinopleVM,
            ADDRESS_NOT_IN_STATE,
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            EMPTY_ADDRESS_IN_STATE,
            '0x0000000000000000000000000000000000000000000000000000000000000000',
        ),
        (
            ConstantinopleVM,
            ADDRESS_WITH_JUST_BALANCE,
            '0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470',
        ),
        (
            ConstantinopleVM,
            ADDRESS_WITH_CODE[0],
            # equivalent to encode_hex(keccak(ADDRESS_WITH_CODE[1])),
            '0xb6f5188e2984211a0de167a56a92d85bee084d7a469d97a59e1e2b573dbb4301'
        ),
    )
)
def test_extcodehash(vm_class, address, expected):
    computation = prepare_general_computation(vm_class)

    computation.stack_push_bytes(decode_hex(address))
    computation.opcodes[opcode_values.EXTCODEHASH](computation)

    result = computation.stack_pop1_bytes()
    assert encode_hex(pad32(result)) == expected


@pytest.mark.parametrize(
    # Testcases from https://eips.ethereum.org/EIPS/eip-1283
    'vm_class, code, gas_used, refund, original',
    (
        (
            ByzantiumVM,
            '0x60006000556000600055',
            10012,
            0,
            0,
        ),
        (
            ByzantiumVM,
            '0x60006000556001600055',
            25012,
            0,
            0,
        ),
        (
            ConstantinopleVM,
            '0x60006000556000600055',
            412,
            0,
            0,
        ),
        (
            ConstantinopleVM,
            '0x60006000556001600055',
            20212,
            0,
            0,
        ),
        (
            ConstantinopleVM,
            '0x60016000556000600055',
            20212,
            19800,
            0,
        ),
        (
            ConstantinopleVM,
            '0x60016000556002600055',
            20212,
            0,
            0,
        ),
        (
            ConstantinopleVM,
            '0x60016000556001600055',
            20212,
            0,
            0,
        ),
        (
            ConstantinopleVM,
            '0x60006000556000600055',
            5212,
            15000,
            1,
        ),
        (
            ConstantinopleVM,
            '0x60006000556001600055',
            5212,
            4800,
            1,
        ),
        (
            ConstantinopleVM,
            '0x60006000556002600055',
            5212,
            0,
            1,
        ),
        (
            ConstantinopleVM,
            '0x60026000556000600055',
            5212,
            15000,
            1,
        ),
        (
            ConstantinopleVM,
            '0x60026000556003600055',
            5212,
            0,
            1,
        ),
        (
            ConstantinopleVM,
            '0x60026000556001600055',
            5212,
            4800,
            1,
        ),
        (
            ConstantinopleVM,
            '0x60026000556002600055',
            5212,
            0,
            1,
        ),
        (
            ConstantinopleVM,
            '0x60016000556000600055',
            5212,
            15000,
            1,
        ),
        (
            ConstantinopleVM,
            '0x60016000556002600055',
            5212,
            0,
            1,
        ),
        (
            ConstantinopleVM,
            '0x60016000556001600055',
            412,
            0,
            1,
        ),
        (
            ConstantinopleVM,
            '0x600160005560006000556001600055',
            40218,
            19800,
            0,
        ),
        (
            ConstantinopleVM,
            '0x600060005560016000556000600055',
            10218,
            19800,
            1,
        ),
        # Petersburg reverts the SSTORE change
        (
            PetersburgVM,
            '0x60006000556000600055',
            10012,
            0,
            0,
        ),
        (
            PetersburgVM,
            '0x60006000556001600055',
            25012,
            0,
            0,
        ),
        # Istanbul re-adds the SSTORE change, but at a higher base cost (200->800)
        (
            IstanbulVM,
            '0x60006000556000600055',
            1612,
            0,
            0,
        ),
        (
            IstanbulVM,
            '0x60006000556001600055',
            20812,
            0,
            0,
        ),
        (
            IstanbulVM,
            '0x60016000556000600055',
            20812,
            19200,
            0,
        ),
        (
            IstanbulVM,
            '0x60016000556002600055',
            20812,
            0,
            0,
        ),
        (
            IstanbulVM,
            '0x60016000556001600055',
            20812,
            0,
            0,
        ),
        (
            IstanbulVM,
            '0x60006000556000600055',
            5812,
            15000,
            1,
        ),
        (
            IstanbulVM,
            '0x60006000556001600055',
            5812,
            4200,
            1,
        ),
        (
            IstanbulVM,
            '0x60006000556002600055',
            5812,
            0,
            1,
        ),
        (
            IstanbulVM,
            '0x60026000556000600055',
            5812,
            15000,
            1,
        ),
        (
            IstanbulVM,
            '0x60026000556003600055',
            5812,
            0,
            1,
        ),
        (
            IstanbulVM,
            '0x60026000556001600055',
            5812,
            4200,
            1,
        ),
        (
            IstanbulVM,
            '0x60026000556002600055',
            5812,
            0,
            1,
        ),
        (
            IstanbulVM,
            '0x60016000556000600055',
            5812,
            15000,
            1,
        ),
        (
            IstanbulVM,
            '0x60016000556002600055',
            5812,
            0,
            1,
        ),
        (
            IstanbulVM,
            '0x60016000556001600055',
            1612,
            0,
            1,
        ),
        (
            IstanbulVM,
            '0x600160005560006000556001600055',
            40818,
            19200,
            0,
        ),
        (
            IstanbulVM,
            '0x600060005560016000556000600055',
            10818,
            19200,
            1,
        ),
    )
)
def test_sstore(vm_class, code, gas_used, refund, original):

    computation = setup_computation(vm_class, CANONICAL_ADDRESS_B, decode_hex(code))

    computation.state.set_balance(CANONICAL_ADDRESS_B, 100000000000)
    computation.state.set_storage(CANONICAL_ADDRESS_B, 0, original)
    assert computation.state.get_storage(CANONICAL_ADDRESS_B, 0) == original
    computation.state.persist()
    assert computation.state.get_storage(CANONICAL_ADDRESS_B, 0, from_journal=True) == original
    assert computation.state.get_storage(CANONICAL_ADDRESS_B, 0, from_journal=False) == original

    comp = computation.apply_message()
    assert comp.get_gas_refund() == refund
    assert comp.get_gas_used() == gas_used


@pytest.mark.parametrize(
    'gas_supplied, success, gas_used, refund',
    (
        # 2 pushes get executed before the SSTORE, so add 6 before checking the 2300 limit
        (2306, False, 2306, 0),
        # Just one more gas, leaving 2301 at the beginning of SSTORE, allows it to succeed
        (2307, True, 806, 0),
    )
)
def test_sstore_limit_2300(gas_supplied, success, gas_used, refund):
    vm_class = IstanbulVM
    hex_code = '0x6000600055'
    original = 0
    computation = setup_computation(
        vm_class,
        CANONICAL_ADDRESS_B,
        decode_hex(hex_code),
        gas=gas_supplied,
    )

    computation.state.set_balance(CANONICAL_ADDRESS_B, 100000000000)
    computation.state.set_storage(CANONICAL_ADDRESS_B, 0, original)
    assert computation.state.get_storage(CANONICAL_ADDRESS_B, 0) == original
    computation.state.persist()

    comp = computation.apply_message()
    if success and not comp.is_success:
        raise comp._error
    else:
        assert comp.is_success == success
    assert comp.get_gas_refund() == refund
    assert comp.get_gas_used() == gas_used


@pytest.mark.parametrize(
    # Testcases from https://eips.ethereum.org/EIPS/eip-1344
    'vm_class, chain_id, expected_result',
    (
        (
            IstanbulVM,
            86,
            86,
        ),
    )
)
def test_chainid(vm_class, chain_id, expected_result):
    computation = prepare_general_computation(vm_class, chain_id=chain_id)

    computation.opcodes[opcode_values.CHAINID](computation)
    result = computation.stack_pop1_any()

    assert result == expected_result
