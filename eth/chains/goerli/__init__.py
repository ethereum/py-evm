from eth_utils import decode_hex

from .constants import (
    BERLIN_GOERLI_BLOCK,
    ISTANBUL_GOERLI_BLOCK,
    PETERSBURG_GOERLI_BLOCK,
)

from eth import constants

from eth.rlp.headers import BlockHeader
from eth.vm.forks import (
    BerlinVM,
    IstanbulVM,
    PetersburgVM,
)

GOERLI_VM_CONFIGURATION = (
    (PETERSBURG_GOERLI_BLOCK, PetersburgVM),
    (ISTANBUL_GOERLI_BLOCK, IstanbulVM),
    (BERLIN_GOERLI_BLOCK, BerlinVM),
)


GOERLI_GENESIS_HEADER = BlockHeader(
    block_number=0,
    bloom=0,
    coinbase=constants.ZERO_ADDRESS,
    difficulty=1,
    extra_data=decode_hex(
        "0x22466c6578692069732061207468696e6722202d204166726900000000000000e0a2bd4258d2768837baa26a28fe71dc079f84c70000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"  # noqa: E501
    ),
    gas_limit=10485760,
    gas_used=0,
    mix_hash=constants.ZERO_HASH32,
    nonce=decode_hex("0x0000000000000000"),
    parent_hash=constants.GENESIS_PARENT_HASH,
    receipt_root=constants.BLANK_ROOT_HASH,
    state_root=decode_hex(
        "0x5d6cded585e73c4e322c30c2f782a336316f17dd85a4863b9d838d2d4b8b3008"
    ),
    timestamp=1548854791,
    transaction_root=constants.BLANK_ROOT_HASH,
    uncles_hash=constants.EMPTY_UNCLE_HASH,
)
