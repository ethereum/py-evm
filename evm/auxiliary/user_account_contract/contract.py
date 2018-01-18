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


# S <= N // 2
MAX_ALLOWED_S = SECPK1_N // 2
VALIDATION_CODE_GAS = 3500
GAS_RESERVE = 4500  # amount of gas reserved for returning
GAS_RESERVE_OFFSET = 200
# standard id for a method with signature `get_nonce()`
NONCE_GETTER_ID = 0x141b5b48
ENTRY_POINT_INT = big_endian_to_int(ENTRY_POINT)

ECRECOVER_ADDRESS = 1
ECRECOVER_GAS = 3000

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


def generate_account_lll_code(address):
    return [
        'seq',

        # handle get_nonce if called
        ['if',
            ['eq',
                ['calldataload', CALLDATA_FUNCTION_ID],
                NONCE_GETTER_ID * 2**224],
            [
                'seq',
                ['mstore', 0, ['sload', STORAGE_NONCE]],
                ['return', 0, 32]
            ]],

        # copy full call data to memory
        ['calldatacopy', MEMORY_CALLDATA, 0, ['calldatasize']],

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
        ['call',
            ECRECOVER_GAS,
            ECRECOVER_ADDRESS,
            0,
            # input data (spans sighash and signature)
            MEMORY_SIGHASH, 128,
            # output data (address)
            MEMORY_SENDER, 32],
        ['with', 'recovered_address', ['mload', MEMORY_SENDER], [
            'seq',
            # check that not zero address has been recovered (this indicates an error)
            ['assert', 'recovered_address'],
            # check that the recovered address is correct
            ['assert', ['eq', 'recovered_address', address]]
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


ADDRESS_PLACEHOLDER = decode_hex('0x0123456789abcdef0123456789abcdef01234567')
# bytecode compiled with `address == ADDRESS_PLACEHOLDER`
# using https://github.com/ethereum/vyper on commit 8588835a9fde8104b3056288886b4b6d9f377973
ACCOUNT_BYTECODE_TEMPLATE = decode_hex(
    "0x7f141b5b4800000000000000000000000000000000000000000000000000000000600"
    "03514156100355760005460005260206000f35b36600060203773ffffffffffffffffff"
    "ffffffffffffffffffffff331461005b57600080fd5b60c03543101561006a57600080f"
    "d5b60e03543111561007957600080fd5b7f7fffffffffffffffffffffffffffffff5d57"
    "6e7357a4501ddfe92f46681b20a1604035106100a757600080fd5b3f366020015260403"
    "603608020600052602060006080600060006001610bb8f150600051806100d557600080"
    "fd5b730123456789abcdef0123456789abcdef0123456781146100f557600080fd5b506"
    "000546060351461010657600080fd5b6001606035016000556114505a1161011d576000"
    "80fd5b608035f55060006000610120360361014060a035610100356113885a03f160005"
    "260206000f3"
)


def generate_account_bytecode(validation_code_address):
    code = ACCOUNT_BYTECODE_TEMPLATE.replace(ADDRESS_PLACEHOLDER, validation_code_address)
    assert len(code) == len(ACCOUNT_BYTECODE_TEMPLATE)
    return code
