from evm.constants import (
    SECPK1_N,
    ENTRY_POINT,
)
from evm.utils.hexadecimal import (
    decode_hex,
)
from evm.utils.numeric import (
    big_endian_to_int,
)
from evm.utils.keccak import (
    keccak,
)


# S <= N // 2
MAX_ALLOWED_S = SECPK1_N // 2
VALIDATION_CODE_GAS = 3500
GAS_RESERVE = 4500  # amount of gas reserved for returning
GAS_RESERVE_OFFSET = 200
NONCE_GETTER_ID = big_endian_to_int(keccak(b"get_nonce()")[:4])
VALIDATION_CODE_GETTER_ID = big_endian_to_int(keccak(b"get_validation_code()")[:4])
ENTRY_POINT_INT = big_endian_to_int(ENTRY_POINT)

SIGNATURE_VERIFICATION_ADDRESS = 1
SIGNATURE_VERIFICATION_GAS = 3000

# calldata locations
CALLDATA_FUNCTION_ID = 0
CALLDATA_SIGNATURE = 0
(
    CALLDATA_V,
    CALLDATA_R,
    CALLDATA_S,
    CALLDATA_NONCE,
    CALLDATA_GASPRICE,
    CALLDATA_VALUE,
    CALLDATA_MIN_BLOCK,
    CALLDATA_MAX_BLOCK,
    CALLDATA_DESTINATION,
    CALLDATA_DATA,
) = (CALLDATA_SIGNATURE + i * 32 for i in range(10))

# memory locations
MEMORY_CALLDATA = 32
MEMORY_NONCE = MEMORY_CALLDATA + CALLDATA_NONCE
MEMORY_DATA = MEMORY_CALLDATA + CALLDATA_DATA
MEMORY_SIGHASH = 0
MEMORY_SENDER = 0
MEMORY_RETURNCODE = 0

# storage locations
STORAGE_NONCE = 0


def generate_account_lll_code(validation_code_address):
    return [
        'seq',

        # handle get_nonce if called
        ['if',
            ['eq',
                ['calldataload', CALLDATA_FUNCTION_ID],
                NONCE_GETTER_ID],
            [
                'seq',
                ['mstore', 0, ['sload', STORAGE_NONCE]],
                ['return', 0, 32]
            ]],

        # copy full call data to memory
        ['calldatacopy', MEMORY_CALLDATA, 0, ['calldatasize']],

        # handle get_validation_code if called
        ['if',
            ['eq',
                ['calldataload', CALLDATA_FUNCTION_ID],
                VALIDATION_CODE_GETTER_ID,
                # return validation code address
                ['mstore', 0, validation_code_address],
                ['return', 12, 20]]],

        # no function is called, so we should be first in the call stack
        ['assert', ['eq', ['caller'], ENTRY_POINT_INT]],

        # check if block is in valid range
        ['assert', ['ge', ['number'], ['calldataload', CALLDATA_MIN_BLOCK]]],
        ['assert', ['le', ['number'], ['calldataload', CALLDATA_MAX_BLOCK]]],

        # Check for small s to avoid malleability
        ['assert', ['lt', ['calldataload', CALLDATA_S], MAX_ALLOWED_S + 1]],

        # load tx-sighash to the end of memory
        ['mstore', ['add', MEMORY_CALLDATA, ['calldatasize']], ['sighash']],
        # Compute sighash = sha3(nonce ++ gasprice ++ value ++ min-block ++ max-block ++ to ++
        # data ++ tx-sighash)
        ['mstore',
            MEMORY_SIGHASH,
            ['sha3', MEMORY_NONCE, ['sub', ['calldatasize'], CALLDATA_NONCE - 32]]],

        # Verify signature by calling validation code
        ['assert',
            [
                'call',
                VALIDATION_CODE_GAS,
                validation_code_address,
                0,
                # input data (spans sighash and signature)
                MEMORY_SIGHASH,
                128,
                # output data (discarded)
                0,
                0
            ]],

        # Verify and increment nonce
        ['assert', ['eq', ['calldataload', CALLDATA_NONCE], ['sload', STORAGE_NONCE]]],
        ['sstore', STORAGE_NONCE, ['add', ['calldataload', CALLDATA_NONCE], 1]],

        # Assert that we won't run out of gas from here on
        ['assert', ['gt', 'gas', GAS_RESERVE + GAS_RESERVE_OFFSET]],

        # Call PAYGAS
        ['paygas', ['calldataload', CALLDATA_GASPRICE]],

        # Make the main call and store status code in memory
        [
            'mstore',
            MEMORY_RETURNCODE,
            [
                'call',
                ['sub', ['gas'], GAS_RESERVE],
                ['calldataload', CALLDATA_DESTINATION],
                ['calldataload', CALLDATA_VALUE],
                # input data range (spans supplied data)
                MEMORY_DATA,
                ['sub', ['calldatasize'], CALLDATA_DATA],
                # output data (discarded)
                0,
                0
            ]
        ],

        ['return', MEMORY_RETURNCODE, 32]
    ]


def generate_validation_lll_code(address):
    return [
        'seq',
        # copy hash and signature to memory
        ['calldatacopy', 0, 0, ['calldatasize']],
        # call ecrecover and store recovered address in memory
        [
            'call',
            SIGNATURE_VERIFICATION_GAS,
            SIGNATURE_VERIFICATION_ADDRESS,
            0,
            0,
            128,
            0,
            32
        ],
        ['with', 'recovered_address', ['mload', 0], [
            'seq',
            # check that not zero address has been recovered (this indicates an error)
            ['assert', ['not', ['iszero', 'recovered_address']]],
            # check that the recovered address is correct
            ['assert', ['eq', 'recovered_address', address]],
            # return 1
            ['mstore', 0, 1],
            ['return', 0, 32]]]
    ]


ADDRESS_PLACEHOLDER = decode_hex('0x0123456789abcdef0123456789abcdef01234567')
# bytecode compiled with `validation_code_address == ADDRESS_PLACEHOLDER`
# using https://github.com/ethereum/vyper on commit 8588835a9fde8104b3056288886b4b6d9f377973
ACCOUNT_BYTECODE_TEMPLATE = decode_hex(
    "0x63141b5b4860003514156100195760005460005260206000f35b36600060203763c66"
    "5b5e2600035141561004b57730123456789abcdef0123456789abcdef01234567600052"
    "6014600cf35b73ffffffffffffffffffffffffffffffffffffffff331461006b5760008"
    "0fd5b60c03543101561007a57600080fd5b60e03543111561008957600080fd5b7f7fff"
    "ffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a160403510610"
    "0b757600080fd5b3f366020015260403603608020600052600060006080600060007301"
    "23456789abcdef0123456789abcdef01234567611194f16100f357600080fd5b6000546"
    "060351461010357600080fd5b6001606035016000556114505a1161011a57600080fd5b"
    "608035f55060006000610120360361014060a035610100356113885a03f160005260206"
    "000f3"
)


# bytecode compiled with `address == ADDRESS_PLACEHOLDER`
# using https://github.com/ethereum/vyper on commit 8588835a9fde8104b3056288886b4b6d9f377973
VALIDATION_BYTECODE_TEMPLATE = decode_hex(
    "0x366000600037602060006080600060006001610bb8f15060005180151961002557600"
    "080fd5b730123456789abcdef0123456789abcdef01234567811461004557600080fd5b"
    "600160005260206000f350"
)


def generate_account_bytecode(validation_code_address):
    code = ACCOUNT_BYTECODE_TEMPLATE.replace(ADDRESS_PLACEHOLDER, validation_code_address)
    assert len(code) == len(ACCOUNT_BYTECODE_TEMPLATE)
    return code


def generate_validation_bytecode(address):
    code = VALIDATION_BYTECODE_TEMPLATE.replace(ADDRESS_PLACEHOLDER, address)
    assert len(code) == len(VALIDATION_BYTECODE_TEMPLATE)
    return code
