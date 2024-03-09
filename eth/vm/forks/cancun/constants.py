HISTORY_BUFFER_LENGTH = 8191
BEACON_ROOTS_ADDRESS = (
    b'\x00\x0f=\xf6\xd72\x80~\xf11\x9f\xb7\xb8\xbb\x85"\xd0\xbe\xac\x02'
)
BEACON_ROOTS_CONTRACT_CODE = b"3s\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xfe\x14`MW` 6\x14`$W__\xfd[_5\x80\x15`IWb\x00\x1f\xff\x81\x06\x90\x81T\x14`<W__\xfd[b\x00\x1f\xff\x01T_R` _\xf3[__\xfd[b\x00\x1f\xffB\x06B\x81U_5\x90b\x00\x1f\xff\x01U\x00"  # noqa: E501

# EIP-4844
BLOB_TX_TYPE = 3
BYTES_PER_FIELD_ELEMENT = 32
FIELD_ELEMENTS_PER_BLOB = 4096
BLS_MODULUS = (
    52435875175126190479447740508185965837690552500527637822603658699938581184513
)
VERSIONED_HASH_VERSION_KZG = b"\x01"
POINT_EVALUATION_PRECOMPILE_ADDRESS = b"\n"
POINT_EVALUATION_PRECOMPILE_GAS = 50_000
MAX_BLOB_GAS_PER_BLOCK = 786_432
TARGET_BLOB_GAS_PER_BLOCK = 393_216
MIN_BLOB_BASE_FEE = 1
BLOB_BASE_FEE_UPDATE_FRACTION = 3_338_477
GAS_PER_BLOB = 2**17
HASH_OPCODE_GAS = 3

# EIP-75416
BASEFEE_OPCODE_GAS = 2
