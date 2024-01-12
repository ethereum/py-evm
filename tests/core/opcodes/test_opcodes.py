import warnings

from eth_utils import (
    ValidationError,
    decode_hex,
    encode_hex,
    hexstr_if_str,
    int_to_big_endian,
    to_bytes,
    to_canonical_address,
)
import pytest

from eth import (
    constants,
)
from eth._utils.address import (
    force_bytes_to_address,
)
from eth._utils.padding import (
    pad32,
)
from eth.chains.mainnet import (
    MAINNET_VMS,
    POS_MAINNET_VMS,
)
from eth.consensus import (
    ConsensusContext,
)
from eth.db.atomic import (
    AtomicDB,
)
from eth.db.chain import (
    ChainDB,
)
from eth.exceptions import (
    InvalidInstruction,
    VMError,
)
from eth.vm import (
    opcode_values,
)
from eth.vm.chain_context import (
    ChainContext,
)
from eth.vm.forks import (
    BerlinVM,
    ByzantiumVM,
    ConstantinopleVM,
    FrontierVM,
    HomesteadVM,
    IstanbulVM,
    LondonVM,
    MuirGlacierVM,
    PetersburgVM,
    ShanghaiVM,
    SpuriousDragonVM,
    TangerineWhistleVM,
)
from eth.vm.forks.shanghai.computation import (
    ShanghaiComputation,
)
from eth.vm.message import (
    Message,
)
from eth.vm.spoof import (
    SpoofTransaction,
)

NORMALIZED_ADDRESS_A = "0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6"
NORMALIZED_ADDRESS_B = "0xcd1722f3947def4cf144679da39c4c32bdc35681"
ADDRESS_WITH_CODE = ("0xddd722f3947def4cf144679da39c4c32bdc35681", b"pseudocode")
EMPTY_ADDRESS_IN_STATE = NORMALIZED_ADDRESS_A
ADDRESS_NOT_IN_STATE = NORMALIZED_ADDRESS_B
ADDRESS_WITH_JUST_BALANCE = "0x0000000000000000000000000000000000000001"
CANONICAL_ADDRESS_A = to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6")
CANONICAL_ADDRESS_B = to_canonical_address("0xcd1722f3947def4cf144679da39c4c32bdc35681")
CANONICAL_ADDRESS_C = b"\xee" * 20
CANONICAL_ZERO_ADDRESS = b"\0" * 20


def assemble(*codes):
    return b"".join(hexstr_if_str(to_bytes, element) for element in codes)


def setup_vm(vm_class, chain_id=None):
    db = AtomicDB()
    chain_context = ChainContext(chain_id)
    genesis_header = vm_class.create_genesis_header(
        difficulty=(
            constants.GENESIS_DIFFICULTY if vm_class not in POS_MAINNET_VMS else 0
        ),
        timestamp=0,
    )
    return vm_class(genesis_header, ChainDB(db), chain_context, ConsensusContext(db))


def run_computation(
    vm,
    create_address,
    code,
    gas=1000000,
    to=CANONICAL_ADDRESS_A,
    transaction_sender=b"\x11" * 20,
    data=b"",
    access_list=None,
):
    executor = vm.state.get_transaction_executor()

    message = Message(
        to=to,
        sender=CANONICAL_ADDRESS_B,
        create_address=create_address,
        value=0,
        data=data,
        code=code,
        gas=gas,
    )
    if access_list is not None:
        txn_builder = vm.get_transaction_builder()
        unsigned_transaction = txn_builder.new_unsigned_access_list_transaction(
            vm.chain_context.chain_id,
            nonce=2,
            gas_price=1,
            gas=gas,
            to=to,
            value=3,
            data=data,
            access_list=access_list,
        )
    else:
        unsigned_transaction = vm.create_unsigned_transaction(
            nonce=2,
            gas_price=1,
            gas=gas,
            to=to,
            value=3,
            data=data,
        )
    transaction = SpoofTransaction(unsigned_transaction, from_=transaction_sender)

    return executor.build_computation(message, transaction)


def run_general_computation(vm_class, create_address=None, code=b"", chain_id=None):
    vm = setup_vm(vm_class, chain_id=chain_id)

    vm.state.touch_account(decode_hex(EMPTY_ADDRESS_IN_STATE))
    vm.state.set_code(decode_hex(ADDRESS_WITH_CODE[0]), ADDRESS_WITH_CODE[1])

    vm.state.set_balance(decode_hex(ADDRESS_WITH_JUST_BALANCE), 1)

    return run_computation(vm, create_address, code)


@pytest.mark.parametrize(
    "vm_class, val1, val2, expected",
    (
        (
            ByzantiumVM,
            2,
            4,
            6,
        ),
        (
            SpuriousDragonVM,
            2,
            4,
            6,
        ),
        (
            TangerineWhistleVM,
            2,
            4,
            6,
        ),
        (
            HomesteadVM,
            2,
            4,
            6,
        ),
        (
            FrontierVM,
            2,
            4,
            6,
        ),
    ),
)
def test_add(vm_class, val1, val2, expected):
    computation = run_general_computation(vm_class)
    computation.stack_push_int(val1)
    computation.stack_push_int(val2)
    computation.opcodes[opcode_values.ADD](computation)

    result = computation.stack_pop1_int()

    assert result == expected


def test_base_fee():
    computation = run_general_computation(LondonVM)
    computation.opcodes[opcode_values.BASEFEE](computation)

    result = computation.stack_pop1_any()

    assert result == 10**9  # 1 gwei


@pytest.mark.parametrize(
    "opcode_value, expected",
    (
        (opcode_values.COINBASE, b"\0" * 20),
        # (opcode_values.TIMESTAMP, 1556826898),
        (opcode_values.NUMBER, 0),
        (opcode_values.DIFFICULTY, 17179869184),
        (opcode_values.GASLIMIT, 5000),
    ),
)
def test_nullary_opcodes(VM, opcode_value, expected):
    computation = run_general_computation(VM)
    computation.opcodes[opcode_value](computation)

    result = computation.stack_pop1_any()

    assert result == expected


@pytest.mark.parametrize(
    "val1, expected",
    (
        (0, b""),
        (1, b""),
        (255, b""),
        (256, b""),
    ),
)
def test_blockhash(VM, val1, expected):
    computation = run_general_computation(VM)
    computation.stack_push_int(val1)
    computation.opcodes[opcode_values.BLOCKHASH](computation)

    result = computation.stack_pop1_any()

    assert result == expected


@pytest.mark.parametrize(
    "vm_class, val1, val2, expected",
    (
        (
            ByzantiumVM,
            2,
            2,
            4,
        ),
        (
            SpuriousDragonVM,
            2,
            2,
            4,
        ),
        (
            TangerineWhistleVM,
            2,
            2,
            4,
        ),
        (
            HomesteadVM,
            2,
            2,
            4,
        ),
        (
            FrontierVM,
            2,
            2,
            4,
        ),
    ),
)
def test_mul(vm_class, val1, val2, expected):
    computation = run_general_computation(vm_class)
    computation.stack_push_int(val1)
    computation.stack_push_int(val2)
    computation.opcodes[opcode_values.MUL](computation)

    result = computation.stack_pop1_int()

    assert result == expected


@pytest.mark.parametrize(
    "vm_class, base, exponent, expected",
    (
        (
            ByzantiumVM,
            0,
            1,
            0,
        ),
        (
            ByzantiumVM,
            0,
            0,
            1,
        ),
        (
            SpuriousDragonVM,
            0,
            1,
            0,
        ),
        (
            SpuriousDragonVM,
            0,
            0,
            1,
        ),
        (
            TangerineWhistleVM,
            0,
            1,
            0,
        ),
        (
            TangerineWhistleVM,
            0,
            0,
            1,
        ),
        (
            HomesteadVM,
            0,
            1,
            0,
        ),
        (
            HomesteadVM,
            0,
            0,
            1,
        ),
        (
            FrontierVM,
            0,
            1,
            0,
        ),
        (
            FrontierVM,
            0,
            0,
            1,
        ),
    ),
)
def test_exp(vm_class, base, exponent, expected):
    computation = run_general_computation(vm_class)
    computation.stack_push_int(exponent)
    computation.stack_push_int(base)
    computation.opcodes[opcode_values.EXP](computation)

    result = computation.stack_pop1_int()

    assert result == expected


@pytest.mark.parametrize(
    # Testcases from https://github.com/ethereum/EIPs/blob/master/EIPS/eip-145.md#shl-shift-left  # noqa: E501
    "vm_class, val1, val2, expected",
    (
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000001",
            "0x00",
            "0x0000000000000000000000000000000000000000000000000000000000000001",
        ),
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000001",
            "0x01",
            "0x0000000000000000000000000000000000000000000000000000000000000002",
        ),
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000001",
            "0xff",
            "0x8000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000001",
            "0x0100",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000001",
            "0x0101",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0x00",
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0x01",
            "0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0xff",
            "0x8000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0x0100",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000000",
            "0x01",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0x01",
            "0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe",
        ),
    ),
)
def test_shl(vm_class, val1, val2, expected):
    computation = run_general_computation(vm_class)
    computation.stack_push_bytes(decode_hex(val1))
    computation.stack_push_bytes(decode_hex(val2))
    computation.opcodes[opcode_values.SHL](computation)

    result = computation.stack_pop1_int()

    assert encode_hex(pad32(int_to_big_endian(result))) == expected


@pytest.mark.parametrize(
    # Cases: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-145.md#shr-logical-shift-right  # noqa: E501
    "vm_class, val1, val2, expected",
    (
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000001",
            "0x00",
            "0x0000000000000000000000000000000000000000000000000000000000000001",
        ),
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000001",
            "0x01",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x8000000000000000000000000000000000000000000000000000000000000000",
            "0x01",
            "0x4000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x8000000000000000000000000000000000000000000000000000000000000000",
            "0xff",
            "0x0000000000000000000000000000000000000000000000000000000000000001",
        ),
        (
            ConstantinopleVM,
            "0x8000000000000000000000000000000000000000000000000000000000000000",
            "0x0100",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x8000000000000000000000000000000000000000000000000000000000000000",
            "0x0101",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0x00",
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0x01",
            "0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0xff",
            "0x0000000000000000000000000000000000000000000000000000000000000001",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0x0100",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000000",
            "0x01",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
    ),
)
def test_shr(vm_class, val1, val2, expected):
    computation = run_general_computation(vm_class)
    computation.stack_push_bytes(decode_hex(val1))
    computation.stack_push_bytes(decode_hex(val2))
    computation.opcodes[opcode_values.SHR](computation)

    result = computation.stack_pop1_int()
    assert encode_hex(pad32(int_to_big_endian(result))) == expected


@pytest.mark.parametrize(
    # EIP: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-145.md#sar-arithmetic-shift-right  # noqa: E501
    "vm_class, val1, val2, expected",
    (
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000001",
            "0x00",
            "0x0000000000000000000000000000000000000000000000000000000000000001",
        ),
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000001",
            "0x01",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x8000000000000000000000000000000000000000000000000000000000000000",
            "0x01",
            "0xc000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x8000000000000000000000000000000000000000000000000000000000000000",
            "0xff",
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
        (
            ConstantinopleVM,
            "0x8000000000000000000000000000000000000000000000000000000000000000",
            "0x0100",
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
        (
            ConstantinopleVM,
            "0x8000000000000000000000000000000000000000000000000000000000000000",
            "0x0101",
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0x00",
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0x01",
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0xff",
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
        (
            ConstantinopleVM,
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0x0100",
            "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ),
        (
            ConstantinopleVM,
            "0x0000000000000000000000000000000000000000000000000000000000000000",
            "0x01",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x4000000000000000000000000000000000000000000000000000000000000000",
            "0xfe",
            "0x0000000000000000000000000000000000000000000000000000000000000001",
        ),
        (
            ConstantinopleVM,
            "0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0xf8",
            "0x000000000000000000000000000000000000000000000000000000000000007f",
        ),
        (
            ConstantinopleVM,
            "0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0xfe",
            "0x0000000000000000000000000000000000000000000000000000000000000001",
        ),
        (
            ConstantinopleVM,
            "0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0xff",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            "0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "0x0100",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
    ),
)
def test_sar(vm_class, val1, val2, expected):
    computation = run_general_computation(vm_class)
    computation.stack_push_bytes(decode_hex(val1))
    computation.stack_push_bytes(decode_hex(val2))
    computation.opcodes[opcode_values.SAR](computation)

    result = computation.stack_pop1_int()
    assert encode_hex(pad32(int_to_big_endian(result))) == expected


@pytest.mark.parametrize(
    "vm_class, address, expected",
    (
        (
            ConstantinopleVM,
            ADDRESS_NOT_IN_STATE,
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            EMPTY_ADDRESS_IN_STATE,
            "0x0000000000000000000000000000000000000000000000000000000000000000",
        ),
        (
            ConstantinopleVM,
            ADDRESS_WITH_JUST_BALANCE,
            "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470",
        ),
        (
            ConstantinopleVM,
            ADDRESS_WITH_CODE[0],
            # equivalent to encode_hex(keccak(ADDRESS_WITH_CODE[1])),
            "0xb6f5188e2984211a0de167a56a92d85bee084d7a469d97a59e1e2b573dbb4301",
        ),
    ),
)
def test_extcodehash(vm_class, address, expected):
    computation = run_general_computation(vm_class)

    computation.stack_push_bytes(decode_hex(address))
    computation.opcodes[opcode_values.EXTCODEHASH](computation)

    result = computation.stack_pop1_bytes()
    assert encode_hex(pad32(result)) == expected


@pytest.mark.parametrize(
    # Testcases from https://eips.ethereum.org/EIPS/eip-1283
    "vm_class, code, gas_used, refund, original",
    (
        (
            ByzantiumVM,
            "0x60006000556000600055",
            10012,
            0,
            0,
        ),
        (
            ByzantiumVM,
            "0x60006000556001600055",
            25012,
            0,
            0,
        ),
        (
            ConstantinopleVM,
            "0x60006000556000600055",
            412,
            0,
            0,
        ),
        (
            ConstantinopleVM,
            "0x60006000556001600055",
            20212,
            0,
            0,
        ),
        (
            ConstantinopleVM,
            "0x60016000556000600055",
            20212,
            19800,
            0,
        ),
        (
            ConstantinopleVM,
            "0x60016000556002600055",
            20212,
            0,
            0,
        ),
        (
            ConstantinopleVM,
            "0x60016000556001600055",
            20212,
            0,
            0,
        ),
        (
            ConstantinopleVM,
            "0x60006000556000600055",
            5212,
            15000,
            1,
        ),
        (
            ConstantinopleVM,
            "0x60006000556001600055",
            5212,
            4800,
            1,
        ),
        (
            ConstantinopleVM,
            "0x60006000556002600055",
            5212,
            0,
            1,
        ),
        (
            ConstantinopleVM,
            "0x60026000556000600055",
            5212,
            15000,
            1,
        ),
        (
            ConstantinopleVM,
            "0x60026000556003600055",
            5212,
            0,
            1,
        ),
        (
            ConstantinopleVM,
            "0x60026000556001600055",
            5212,
            4800,
            1,
        ),
        (
            ConstantinopleVM,
            "0x60026000556002600055",
            5212,
            0,
            1,
        ),
        (
            ConstantinopleVM,
            "0x60016000556000600055",
            5212,
            15000,
            1,
        ),
        (
            ConstantinopleVM,
            "0x60016000556002600055",
            5212,
            0,
            1,
        ),
        (
            ConstantinopleVM,
            "0x60016000556001600055",
            412,
            0,
            1,
        ),
        (
            ConstantinopleVM,
            "0x600160005560006000556001600055",
            40218,
            19800,
            0,
        ),
        (
            ConstantinopleVM,
            "0x600060005560016000556000600055",
            10218,
            19800,
            1,
        ),
        # Petersburg reverts the SSTORE change
        (
            PetersburgVM,
            "0x60006000556000600055",
            10012,
            0,
            0,
        ),
        (
            PetersburgVM,
            "0x60006000556001600055",
            25012,
            0,
            0,
        ),
        # Istanbul re-adds the SSTORE change, but at a higher base cost (200->800)
        (
            IstanbulVM,
            "0x60006000556000600055",
            1612,
            0,
            0,
        ),
        (
            IstanbulVM,
            "0x60006000556001600055",
            20812,
            0,
            0,
        ),
        (
            IstanbulVM,
            "0x60016000556000600055",
            20812,
            19200,
            0,
        ),
        (
            IstanbulVM,
            "0x60016000556002600055",
            20812,
            0,
            0,
        ),
        (
            IstanbulVM,
            "0x60016000556001600055",
            20812,
            0,
            0,
        ),
        (
            IstanbulVM,
            "0x60006000556000600055",
            5812,
            15000,
            1,
        ),
        (
            IstanbulVM,
            "0x60006000556001600055",
            5812,
            4200,
            1,
        ),
        (
            IstanbulVM,
            "0x60006000556002600055",
            5812,
            0,
            1,
        ),
        (
            IstanbulVM,
            "0x60026000556000600055",
            5812,
            15000,
            1,
        ),
        (
            IstanbulVM,
            "0x60026000556003600055",
            5812,
            0,
            1,
        ),
        (
            IstanbulVM,
            "0x60026000556001600055",
            5812,
            4200,
            1,
        ),
        (
            IstanbulVM,
            "0x60026000556002600055",
            5812,
            0,
            1,
        ),
        (
            IstanbulVM,
            "0x60016000556000600055",
            5812,
            15000,
            1,
        ),
        (
            IstanbulVM,
            "0x60016000556002600055",
            5812,
            0,
            1,
        ),
        (
            IstanbulVM,
            "0x60016000556001600055",
            1612,
            0,
            1,
        ),
        (
            IstanbulVM,
            "0x600160005560006000556001600055",
            40818,
            19200,
            0,
        ),
        (
            IstanbulVM,
            "0x600060005560016000556000600055",
            10818,
            19200,
            1,
        ),
        # No changes in Muir Glacier
        (
            MuirGlacierVM,
            "0x60006000556000600055",
            1612,
            0,
            0,
        ),
        (
            MuirGlacierVM,
            "0x60006000556001600055",
            20812,
            0,
            0,
        ),
        (
            MuirGlacierVM,
            "0x60016000556000600055",
            20812,
            19200,
            0,
        ),
        (
            MuirGlacierVM,
            "0x60016000556002600055",
            20812,
            0,
            0,
        ),
        (
            MuirGlacierVM,
            "0x60016000556001600055",
            20812,
            0,
            0,
        ),
        (
            MuirGlacierVM,
            "0x60006000556000600055",
            5812,
            15000,
            1,
        ),
        (
            MuirGlacierVM,
            "0x60006000556001600055",
            5812,
            4200,
            1,
        ),
        (
            MuirGlacierVM,
            "0x60006000556002600055",
            5812,
            0,
            1,
        ),
        (
            MuirGlacierVM,
            "0x60026000556000600055",
            5812,
            15000,
            1,
        ),
        (
            MuirGlacierVM,
            "0x60026000556003600055",
            5812,
            0,
            1,
        ),
        (
            MuirGlacierVM,
            "0x60026000556001600055",
            5812,
            4200,
            1,
        ),
        (
            MuirGlacierVM,
            "0x60026000556002600055",
            5812,
            0,
            1,
        ),
        (
            MuirGlacierVM,
            "0x60016000556000600055",
            5812,
            15000,
            1,
        ),
        (
            MuirGlacierVM,
            "0x60016000556002600055",
            5812,
            0,
            1,
        ),
        (
            MuirGlacierVM,
            "0x60016000556001600055",
            1612,
            0,
            1,
        ),
        (
            MuirGlacierVM,
            "0x600160005560006000556001600055",
            40818,
            19200,
            0,
        ),
        (
            MuirGlacierVM,
            "0x600060005560016000556000600055",
            10818,
            19200,
            1,
        ),
        # London reduces refund by changing SSTORE_CLEARS_SCHEDULE
        # Test cases from: https://eips.ethereum.org/EIPS/eip-3529
        # Note: test cases assume the storage slot is already warm,
        # the difference being a one-time cost of 2100 gas.
        # so gas_used becomes gas_used from EIP-3529 test case + 2100
        (
            LondonVM,
            "0x60006000556000600055",
            212 + 2100,
            0,
            0,
        ),
        (
            LondonVM,
            "0x60006000556001600055",
            20112 + 2100,
            0,
            0,
        ),
        (
            LondonVM,
            "0x60016000556000600055",
            20112 + 2100,
            19900,
            0,
        ),
        (
            LondonVM,
            "0x60016000556002600055",
            20112 + 2100,
            0,
            0,
        ),
        (
            LondonVM,
            "0x60016000556001600055",
            20112 + 2100,
            0,
            0,
        ),
        (
            LondonVM,
            "0x60006000556000600055",
            3012 + 2100,
            4800,
            1,
        ),
        (
            LondonVM,
            "0x60006000556001600055",
            3012 + 2100,
            2800,
            1,
        ),
        (
            LondonVM,
            "0x60006000556002600055",
            3012 + 2100,
            0,
            1,
        ),
        (
            LondonVM,
            "0x60026000556000600055",
            3012 + 2100,
            4800,
            1,
        ),
        (
            LondonVM,
            "0x60026000556003600055",
            3012 + 2100,
            0,
            1,
        ),
        (
            LondonVM,
            "0x60026000556001600055",
            3012 + 2100,
            2800,
            1,
        ),
        (
            LondonVM,
            "0x60026000556002600055",
            3012 + 2100,
            0,
            1,
        ),
        (
            LondonVM,
            "0x60016000556000600055",
            3012 + 2100,
            4800,
            1,
        ),
        (
            LondonVM,
            "0x60016000556002600055",
            3012 + 2100,
            0,
            1,
        ),
        (
            LondonVM,
            "0x60016000556001600055",
            212 + 2100,
            0,
            1,
        ),
        (
            LondonVM,
            "0x600160005560006000556001600055",
            40118 + 2100,
            19900,
            0,
        ),
        (
            LondonVM,
            "0x600060005560016000556000600055",
            5918 + 2100,
            7600,
            1,
        ),
    ),
)
def test_sstore(vm_class, code, gas_used, refund, original):
    vm = setup_vm(vm_class)

    vm.state.set_balance(CANONICAL_ADDRESS_B, 100000000000)
    vm.state.set_storage(CANONICAL_ADDRESS_B, 0, original)
    assert vm.state.get_storage(CANONICAL_ADDRESS_B, 0) == original
    vm.state.persist()
    assert vm.state.get_storage(CANONICAL_ADDRESS_B, 0, from_journal=True) == original
    assert vm.state.get_storage(CANONICAL_ADDRESS_B, 0, from_journal=False) == original

    comp = run_computation(vm, CANONICAL_ADDRESS_B, decode_hex(code))
    assert comp.get_gas_refund() == refund
    assert comp.get_gas_used() == gas_used


@pytest.mark.parametrize(
    "gas_supplied, success, gas_used, refund",
    (
        # 2 pushes get executed before the SSTORE,
        # so add 6 before checking the 2300 limit
        (2306, False, 2306, 0),
        # Just one more gas, leaving 2301 at the beginning
        # of SSTORE, allows it to succeed
        (2307, True, 806, 0),
    ),
)
def test_sstore_limit_2300(gas_supplied, success, gas_used, refund):
    vm_class = IstanbulVM
    hex_code = "0x6000600055"
    original = 0
    vm = setup_vm(vm_class)

    vm.state.set_balance(CANONICAL_ADDRESS_B, 100000000000)
    vm.state.set_storage(CANONICAL_ADDRESS_B, 0, original)
    assert vm.state.get_storage(CANONICAL_ADDRESS_B, 0) == original
    vm.state.persist()

    comp = run_computation(
        vm,
        CANONICAL_ADDRESS_B,
        decode_hex(hex_code),
        gas=gas_supplied,
    )
    if success and not comp.is_success:
        raise comp._error
    else:
        assert comp.is_success == success
    assert comp.get_gas_refund() == refund
    assert comp.get_gas_used() == gas_used


@pytest.mark.parametrize(
    "vm_class",
    (
        IstanbulVM,
        MuirGlacierVM,
        BerlinVM,
        LondonVM,
    ),
)
@pytest.mark.parametrize(
    # Testcases from https://eips.ethereum.org/EIPS/eip-1344
    "chain_id, expected_result",
    (
        (
            86,
            86,
        ),
        (
            0,
            0,
        ),
        (
            -1,
            ValidationError,
        ),
        (
            2**256 - 1,
            2**256 - 1,
        ),
        (
            2**256,
            ValidationError,
        ),
    ),
)
def test_chainid(vm_class, chain_id, expected_result):
    if not isinstance(expected_result, int):
        with pytest.raises(expected_result):
            computation = run_general_computation(vm_class, chain_id=chain_id)
        return

    computation = run_general_computation(vm_class, chain_id=chain_id)

    computation.opcodes[opcode_values.CHAINID](computation)
    result = computation.stack_pop1_any()

    assert result == expected_result


@pytest.mark.parametrize(
    "vm_class, code, expect_exception, expect_gas_used",
    (
        (
            ConstantinopleVM,
            assemble(
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_B,
                opcode_values.BALANCE,
            ),
            None,
            3 + 400,
        ),
        (
            ConstantinopleVM,
            assemble(
                opcode_values.SELFBALANCE,
            ),
            InvalidInstruction,
            # the invalid instruction causes a failure that consumes all provided gas
            1_000_000,
        ),
        (
            IstanbulVM,
            assemble(
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_B,
                opcode_values.BALANCE,
            ),
            None,
            3 + 700,  # balance now costs more
        ),
        (
            IstanbulVM,
            assemble(
                opcode_values.SELFBALANCE,
            ),
            None,
            5,
        ),
        (
            MuirGlacierVM,
            assemble(
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_B,
                opcode_values.BALANCE,
            ),
            None,
            3 + 700,  # balance now costs more
        ),
        (
            MuirGlacierVM,
            assemble(
                opcode_values.SELFBALANCE,
            ),
            None,
            5,
        ),
        (
            BerlinVM,
            assemble(
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_B,
                opcode_values.BALANCE,
            ),
            None,
            # The balance is cheap because the address is marked as accessed,
            # as the transaction recipient
            3 + 100,
        ),
        (
            BerlinVM,
            assemble(
                opcode_values.SELFBALANCE,
            ),
            None,
            5,
        ),
    ),
)
def test_balance(vm_class, code, expect_exception, expect_gas_used):
    sender_balance = 987654321
    vm = setup_vm(vm_class)

    vm.state.set_balance(CANONICAL_ADDRESS_B, sender_balance)
    vm.state.persist()

    comp = run_computation(vm, CANONICAL_ADDRESS_B, code)

    # make sure setup is correct
    assert comp.msg.sender == CANONICAL_ADDRESS_B

    if expect_exception:
        assert isinstance(comp.error, expect_exception)
    else:
        assert comp.is_success
        assert comp.stack_pop1_int() == sender_balance

    assert len(comp._stack) == 0
    assert comp.get_gas_used() == expect_gas_used


@pytest.mark.parametrize(
    "vm_class, code, expect_gas_used",
    (
        (
            ConstantinopleVM,
            assemble(
                opcode_values.PUSH1,
                0x0,
                opcode_values.SLOAD,
            ),
            3 + 200,
        ),
        (
            ConstantinopleVM,
            assemble(
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_A,
                opcode_values.EXTCODEHASH,
            ),
            3 + 400,
        ),
        (
            IstanbulVM,
            assemble(
                opcode_values.PUSH1,
                0x0,
                opcode_values.SLOAD,
            ),
            3 + 800,
        ),
        (
            IstanbulVM,
            assemble(
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_A,
                opcode_values.EXTCODEHASH,
            ),
            3 + 700,
        ),
        (
            MuirGlacierVM,
            assemble(
                opcode_values.PUSH1,
                0x0,
                opcode_values.SLOAD,
            ),
            3 + 800,
        ),
        (
            MuirGlacierVM,
            assemble(
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_A,
                opcode_values.EXTCODEHASH,
            ),
            3 + 700,
        ),
        # first sload should use the cold cost
        (
            BerlinVM,
            assemble(
                opcode_values.PUSH1,
                0x0,
                opcode_values.SLOAD,
            ),
            3 + 2100,
        ),
        # querying the same address twice results in a
        # cold cost and a warm cost
        (
            BerlinVM,
            assemble(
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_C,
                opcode_values.BALANCE,
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_C,
                opcode_values.BALANCE,
            ),
            3 + 2600 + 3 + 100,
        ),
        # querying two different addresses results in two
        # cold costs
        (
            BerlinVM,
            assemble(
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_C,
                opcode_values.BALANCE,
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_A,
                opcode_values.BALANCE,
            ),
            3 + 2600 + 3 + 2600,
        ),
        # precompiles are exempt from cold cost
        (
            BerlinVM,
            assemble(
                opcode_values.PUSH20,
                force_bytes_to_address(b"\x05"),
                opcode_values.BALANCE,
            ),
            3 + 100,
        ),
    ),
)
def test_gas_costs(vm_class, code, expect_gas_used):
    comp = run_computation(setup_vm(vm_class), CANONICAL_ADDRESS_B, code)
    assert comp.is_success
    assert comp.get_gas_used() == expect_gas_used


@pytest.mark.parametrize(
    "vm_class, code, expect_gas_used, access_list",
    (
        # Empty access list does not affect account cache warmth
        (
            BerlinVM,
            assemble(
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_C,
                opcode_values.BALANCE,
            ),
            3 + 2600,
            [],
        ),
        # Access list pre-warms account cache
        (
            BerlinVM,
            assemble(
                opcode_values.PUSH20,
                CANONICAL_ADDRESS_C,
                opcode_values.BALANCE,
            ),
            3 + 100,
            [(CANONICAL_ADDRESS_C, [])],
        ),
        # Access list pre-warms storage cache
        (
            BerlinVM,
            assemble(
                opcode_values.PUSH1,
                0x0,
                opcode_values.SLOAD,
                opcode_values.PUSH1,
                0x1,
                opcode_values.SLOAD,
            ),
            3 + 100 + 3 + 2100,
            [(CANONICAL_ZERO_ADDRESS, [0])],
        ),
    ),
)
def test_access_list_gas_costs(vm_class, code, expect_gas_used, access_list):
    recipient = CANONICAL_ZERO_ADDRESS
    comp = run_computation(
        setup_vm(vm_class),
        recipient,
        code,
        to=recipient,
        access_list=access_list,
        transaction_sender=CANONICAL_ZERO_ADDRESS,
    )
    assert comp.is_success
    assert comp.get_gas_used() == expect_gas_used


# cases from https://gist.github.com/holiman/174548cad102096858583c6fbbb0649a
# mentioned in EIP-2929
@pytest.mark.parametrize(
    "vm_class",
    (
        BerlinVM,
        LondonVM,
    ),
)
@pytest.mark.parametrize(
    "bytecode_hex, expect_gas_used",
    (
        (
            "0x60013f5060023b506003315060f13f5060f23b5060f3315060f23f5060f33b5060f1315032315030315000",  # noqa: E501
            8653,
        ),
        (
            "0x60006000600060ff3c60006000600060ff3c600060006000303c00",
            2835,
        ),
        (
            "0x60015450601160015560116002556011600255600254600154",
            44529,
        ),
        (
            "0x60008080808060046000f15060008080808060ff6000f15060008080808060ff6000fa50",  # noqa: E501
            2869,
        ),
    ),
)
def test_eip2929_gas_by_cache_warmth(vm_class, bytecode_hex, expect_gas_used):
    recipient = decode_hex("0x000000000000000000000000636F6E7472616374")
    comp = run_computation(
        setup_vm(vm_class),
        recipient,
        decode_hex(bytecode_hex),
        gas=18446744073709551615,
        to=recipient,
        transaction_sender=b"\0" * 20,  # sender defined as 0 address in these tests
    )

    assert comp.is_success
    assert comp.get_gas_used() == expect_gas_used


@pytest.mark.parametrize(
    "vm_class, input_hex, output_hex, expect_exception",
    (
        (
            PetersburgVM,
            "0000000048c9bdf267e6096a3ba7ca8485ae67bb2bf894fe72f36e3cf1361d5f3af54fa5d182e6ad7f520e511f6c3e2b8c68059b6bbd41fbabd9831f79217e1319cde05b61626300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000001",  # noqa: E501
            "",
            None,
        ),
        (
            IstanbulVM,
            "",
            "",
            VMError,
        ),
        (
            IstanbulVM,
            "00000c48c9bdf267e6096a3ba7ca8485ae67bb2bf894fe72f36e3cf1361d5f3af54fa5d182e6ad7f520e511f6c3e2b8c68059b6bbd41fbabd9831f79217e1319cde05b61626300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000001",  # noqa: E501
            "",
            VMError,
        ),
        (
            IstanbulVM,
            "000000000c48c9bdf267e6096a3ba7ca8485ae67bb2bf894fe72f36e3cf1361d5f3af54fa5d182e6ad7f520e511f6c3e2b8c68059b6bbd41fbabd9831f79217e1319cde05b61626300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000001",  # noqa: E501
            "",
            VMError,
        ),
        (
            IstanbulVM,
            "0000000c48c9bdf267e6096a3ba7ca8485ae67bb2bf894fe72f36e3cf1361d5f3af54fa5d182e6ad7f520e511f6c3e2b8c68059b6bbd41fbabd9831f79217e1319cde05b61626300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000002",  # noqa: E501
            "",
            VMError,
        ),
        (
            IstanbulVM,
            "0000000048c9bdf267e6096a3ba7ca8485ae67bb2bf894fe72f36e3cf1361d5f3af54fa5d182e6ad7f520e511f6c3e2b8c68059b6bbd41fbabd9831f79217e1319cde05b61626300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000001",  # noqa: E501
            "08c9bcf367e6096a3ba7ca8485ae67bb2bf894fe72f36e3cf1361d5f3af54fa5d282e6ad7f520e511f6c3e2b8c68059b9442be0454267ce079217e1319cde05b",  # noqa: E501
            None,
        ),
        (
            IstanbulVM,
            "0000000c48c9bdf267e6096a3ba7ca8485ae67bb2bf894fe72f36e3cf1361d5f3af54fa5d182e6ad7f520e511f6c3e2b8c68059b6bbd41fbabd9831f79217e1319cde05b61626300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000001",  # noqa: E501
            "ba80a53f981c4d0d6a2797b69f12f6e94c212f14685ac4b74b12bb6fdbffa2d17d87c5392aab792dc252d5de4533cc9518d38aa8dbf1925ab92386edd4009923",  # noqa: E501
            None,
        ),
        (
            IstanbulVM,
            "0000000c48c9bdf267e6096a3ba7ca8485ae67bb2bf894fe72f36e3cf1361d5f3af54fa5d182e6ad7f520e511f6c3e2b8c68059b6bbd41fbabd9831f79217e1319cde05b61626300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000000",  # noqa: E501
            "75ab69d3190a562c51aef8d88f1c2775876944407270c42c9844252c26d2875298743e7f6d5ea2f2d3e8d226039cd31b4e426ac4f2d3d666a610c2116fde4735",  # noqa: E501
            None,
        ),
        (
            IstanbulVM,
            "0000000148c9bdf267e6096a3ba7ca8485ae67bb2bf894fe72f36e3cf1361d5f3af54fa5d182e6ad7f520e511f6c3e2b8c68059b6bbd41fbabd9831f79217e1319cde05b61626300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000001",  # noqa: E501
            "b63a380cb2897d521994a85234ee2c181b5f844d2c624c002677e9703449d2fba551b3a8333bcdf5f2f7e08993d53923de3d64fcc68c034e717b9293fed7a421",  # noqa: E501
            None,
        ),
        pytest.param(
            IstanbulVM,
            "ffffffff48c9bdf267e6096a3ba7ca8485ae67bb2bf894fe72f36e3cf1361d5f3af54fa5d182e6ad7f520e511f6c3e2b8c68059b6bbd41fbabd9831f79217e1319cde05b61626300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000300000000000000000000000000000001",  # noqa: E501
            "fc59093aafa9ab43daae0e914c57635c5402d8e3d2130eb9b3cc181de7f0ecf9b22bf99a7815ce16419e200e01846e6b5df8cc7703041bbceb571de6631d2615",  # noqa: E501
            None,
            marks=pytest.mark.skip(
                reason="Takes 90s to run against blake2b-py v0.1.2, but passes!"
            ),
        ),
    ),
)
def test_blake2b_f_compression(vm_class, input_hex, output_hex, expect_exception):
    comp = run_computation(
        setup_vm(vm_class),
        CANONICAL_ADDRESS_B,
        code=b"",
        gas=2**32 - 1,
        to=force_bytes_to_address(b"\x09"),
        data=to_bytes(hexstr=input_hex),
    )

    if expect_exception:
        assert isinstance(comp.error, expect_exception)
    else:
        comp.raise_if_error()
        result = comp.output
        assert result.hex() == output_hex


@pytest.mark.parametrize("vm_class", MAINNET_VMS[:13])  # vms up to Shanghai
def test_selfdestruct_does_not_issue_deprecation_warning_pre_shanghai(vm_class):
    # assert no warning without selfdestruct
    with warnings.catch_warnings():
        warnings.simplefilter("error")

        run_computation(
            setup_vm(vm_class),
            CANONICAL_ADDRESS_B,
            code=assemble(opcode_values.SELFDESTRUCT),
        )


def test_selfdestruct_issues_deprecation_warning_for_shanghai():
    available_vm_opcodes = ShanghaiComputation.opcodes

    vm_opcodes_without_selfdestruct = {
        k: available_vm_opcodes[k]
        for k in available_vm_opcodes.keys()
        if k != opcode_values.SELFDESTRUCT
    }
    code_without_self_destruct = assemble(
        *[opc for opc in vm_opcodes_without_selfdestruct.keys()]
    )

    # assert no warning using every opcode except selfdestruct
    with warnings.catch_warnings():
        warnings.simplefilter("error")

        run_computation(
            setup_vm(ShanghaiVM),
            CANONICAL_ADDRESS_B,
            code=code_without_self_destruct,
        )

    # assert warning with just selfdestruct opcode
    with pytest.warns(DeprecationWarning):
        run_computation(
            setup_vm(ShanghaiVM),
            CANONICAL_ADDRESS_B,
            code=assemble(opcode_values.SELFDESTRUCT),
        )
