# WARNING: untested and thus broken by assumption


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
SIGNATURE_VERIFICATION_ADDRESS = 1
SIGNATURE_VERIFICATION_GAS = 3000
GAS_RESERVE = 5000  # amount of gas reserved for returning
GAS_RESERVE_OFFSET = 200
NONCE_GETTER_ID = big_endian_to_int(keccak(b"get_nonce()")[:4])
VALIDATION_GETTER_ID = big_endian_to_int(keccak(b"get_validation_code()")[:4])
ENTRY_POINT_INT = big_endian_to_int(ENTRY_POINT)

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


def generate_lll_code(address, validation_code_address=SIGNATURE_VERIFICATION_ADDRESS):
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
                VALIDATION_GETTER_ID],
            [
                'seq',
                [
                    'call',
                    SIGNATURE_VERIFICATION_GAS,
                    validation_code_address,
                    0,
                    4,  # pass everything except function signature
                    ['sub', ['calldatasize'], 4],
                    MEMORY_SENDER,
                    32
                ],
                ['assert', ['eq', ['mload', MEMORY_SENDER], address]]
            ]],

        # no function is called, so we should be first in the call stack
        ['assert', ['eq', ['caller'], ENTRY_POINT_INT]],

        # check if block is in valid range
        ['assert', ['ge', ['number'], ['calldataload', CALLDATA_MIN_BLOCK]]],
        ['assert', ['le', ['number'], ['calldataload', CALLDATA_MAX_BLOCK]]],

        # Check for small s to avoid malleability
        ['assert', ['lt', ['calldataload', CALLDATA_S], MAX_ALLOWED_S + 1]],

        # TODO: check for insufficient funds or not?

        # load tx-sighash to the end of memory
        ['mstore', ['add', MEMORY_CALLDATA, ['calldatasize']], ['sighash']],
        # Compute sighash = sha3(nonce ++ gasprice ++ value ++ min-block ++ max-block ++ to ++
        # data ++ tx-sighash)
        ['mstore',
            MEMORY_SIGHASH,
            ['sha3', MEMORY_NONCE, ['sub', ['calldatasize'], CALLDATA_NONCE - 32]]],

        # Verify signature
        [
            'call',
            SIGNATURE_VERIFICATION_GAS,
            SIGNATURE_VERIFICATION_ADDRESS,
            0,                               # value
            MEMORY_SIGHASH,                  # input data start
            128,                             # input data length (spans sighash and signature)
            MEMORY_SENDER,                   # output data start
            32                               # output data length
        ],
        ['assert', ['eq', ['mload', MEMORY_SENDER], address]],

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


ADDRESS_PLACEHOLDER = decode_hex('0x0123456789abcdef0123456789abcdef01234567')
# bytecode compiled with `address == ADDRESS_PLACEHOLDER`
BYTECODE_TEMPLATE = decode_hex(
    "0x63141b5b4860003514156100195760005460005260206000f35b36600060203763c66"
    "5b5e26000351415610063576020600060043603600460006001610bb8f1507301234567"
    "89abcdef0123456789abcdef012345676000511461006257600080fd5b5b73fffffffff"
    "fffffffffffffffffffffffffffffff331461008357600080fd5b60c035431015610092"
    "57600080fd5b60e0354311156100a157600080fd5b7f7ffffffffffffffffffffffffff"
    "fffff5d576e7357a4501ddfe92f46681b20a1604035106100cf57600080fd5b3f366020"
    "015260403603608020600052602060006080600060006001610bb8f150730123456789a"
    "bcdef0123456789abcdef012345676000511461011257600080fd5b6000546060351461"
    "012257600080fd5b6001606035016000556114505a1161013957600080fd5b608035f55"
    "060006000610120360361014060a035610100356113885a03f160005260206000f3"
)


def generate_bytecode(address):
    code = BYTECODE_TEMPLATE.replace(ADDRESS_PLACEHOLDER, address)
    assert len(code) == len(BYTECODE_TEMPLATE)
    return code
