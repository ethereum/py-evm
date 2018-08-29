from typing import Tuple, Type  # noqa: F401

from eth_utils import (
    decode_hex,
    encode_hex,
    ValidationError,
)

from .constants import (
    BYZANTIUM_MAINNET_BLOCK,
    TANGERINE_WHISTLE_MAINNET_BLOCK,
    HOMESTEAD_MAINNET_BLOCK,
    SPURIOUS_DRAGON_MAINNET_BLOCK,
    DAO_FORK_MAINNET_EXTRA_DATA,
)
from eth import constants

from eth.chains.base import (
    Chain,
)
from eth.rlp.headers import BlockHeader
from eth.vm.base import BaseVM  # noqa: F401
from eth.vm.forks import (
    TangerineWhistleVM,
    FrontierVM,
    HomesteadVM,
    SpuriousDragonVM,
    ByzantiumVM,
)


class MainnetDAOValidatorVM:
    """Only on mainnet, TheDAO fork is accompanied by special extra data. Validate those headers"""

    @classmethod
    def validate_header(cls, header, previous_header, check_seal=True):
        # ignore mypy warnings, because super's validate_header is defined by mixing w/ other class
        super().validate_header(header, previous_header, check_seal)  # type: ignore

        # The special extra_data is set on the ten headers starting at the fork
        extra_data_block_nums = range(cls.dao_fork_block_number, cls.dao_fork_block_number + 10)

        if header.block_number in extra_data_block_nums:
            if cls.support_dao_fork and header.extra_data != DAO_FORK_MAINNET_EXTRA_DATA:
                raise ValidationError(
                    "Block {!r} must have extra data {} not {} when supporting DAO fork".format(
                        header,
                        encode_hex(DAO_FORK_MAINNET_EXTRA_DATA),
                        encode_hex(header.extra_data),
                    )
                )
            elif not cls.support_dao_fork and header.extra_data == DAO_FORK_MAINNET_EXTRA_DATA:
                raise ValidationError(
                    "Block {!r} must not have extra data {} when declining the DAO fork".format(
                        header,
                        encode_hex(DAO_FORK_MAINNET_EXTRA_DATA),
                    )
                )


class MainnetHomesteadVM(MainnetDAOValidatorVM, HomesteadVM):
    pass


MAINNET_FORK_BLOCKS = (
    0,
    HOMESTEAD_MAINNET_BLOCK,
    TANGERINE_WHISTLE_MAINNET_BLOCK,
    SPURIOUS_DRAGON_MAINNET_BLOCK,
    BYZANTIUM_MAINNET_BLOCK,
)
MAINNET_VMS = (
    FrontierVM,
    MainnetHomesteadVM,
    TangerineWhistleVM,
    SpuriousDragonVM,
    ByzantiumVM,
)

MAINNET_VM_CONFIGURATION = tuple(zip(MAINNET_FORK_BLOCKS, MAINNET_VMS))

MAINNET_NETWORK_ID = 1


class BaseMainnetChain:
    vm_configuration = MAINNET_VM_CONFIGURATION  # type: Tuple[Tuple[int, Type[BaseVM]], ...]
    network_id = MAINNET_NETWORK_ID  # type: int


class MainnetChain(BaseMainnetChain, Chain):
    pass


MAINNET_GENESIS_HEADER = BlockHeader(
    difficulty=17179869184,
    extra_data=decode_hex("0x11bbe8db4e347b4e8c937c1c8370e4b5ed33adb3db69cbdb7a38e1e50b1b82fa"),
    gas_limit=5000,
    gas_used=0,
    bloom=0,
    mix_hash=constants.ZERO_HASH32,
    nonce=constants.GENESIS_NONCE,
    block_number=0,
    parent_hash=constants.ZERO_HASH32,
    receipt_root=constants.BLANK_ROOT_HASH,
    uncles_hash=constants.EMPTY_UNCLE_HASH,
    state_root=decode_hex("0xd7f8974fb5ac78d9ac099b9ad5018bedc2ce0a72dad1827a1709da30580f0544"),
    timestamp=0,
    transaction_root=constants.BLANK_ROOT_HASH,
)
