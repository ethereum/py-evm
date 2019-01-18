from typing import (    # noqa: F401
    Tuple,
    Type,
    TypeVar,
)

from eth_utils import (
    decode_hex,
    encode_hex,
    ValidationError,
)

from .constants import (
    MAINNET_CHAIN_ID,
    BYZANTIUM_MAINNET_BLOCK,
    PETERSBURG_MAINNET_BLOCK,
    TANGERINE_WHISTLE_MAINNET_BLOCK,
    HOMESTEAD_MAINNET_BLOCK,
    SPURIOUS_DRAGON_MAINNET_BLOCK,
    DAO_FORK_MAINNET_EXTRA_DATA,
    DAO_FORK_MAINNET_BLOCK,
)
from eth import constants as eth_constants

from eth.chains.base import (
    Chain,
)
from eth.rlp.headers import BlockHeader
from eth.vm.base import BaseVM  # noqa: F401
from eth.vm.forks import (
    ByzantiumVM,
    FrontierVM,
    HomesteadVM,
    PetersburgVM,
    SpuriousDragonVM,
    TangerineWhistleVM,
)


class MainnetDAOValidatorVM(HomesteadVM):
    """Only on mainnet, TheDAO fork is accompanied by special extra data. Validate those headers"""

    @classmethod
    def validate_header(cls,
                        header: BlockHeader,
                        previous_header: BlockHeader,
                        check_seal: bool=True) -> None:

        super().validate_header(header, previous_header, check_seal)

        # The special extra_data is set on the ten headers starting at the fork
        dao_fork_at = cls.get_dao_fork_block_number()
        extra_data_block_nums = range(dao_fork_at, dao_fork_at + 10)

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


class MainnetHomesteadVM(MainnetDAOValidatorVM):
    _dao_fork_block_number = DAO_FORK_MAINNET_BLOCK


MAINNET_FORK_BLOCKS = (
    0,
    HOMESTEAD_MAINNET_BLOCK,
    TANGERINE_WHISTLE_MAINNET_BLOCK,
    SPURIOUS_DRAGON_MAINNET_BLOCK,
    BYZANTIUM_MAINNET_BLOCK,
    PETERSBURG_MAINNET_BLOCK,
)
MAINNET_VMS = (
    FrontierVM,
    MainnetHomesteadVM,
    TangerineWhistleVM,
    SpuriousDragonVM,
    ByzantiumVM,
    PetersburgVM,
)

MAINNET_VM_CONFIGURATION = tuple(zip(MAINNET_FORK_BLOCKS, MAINNET_VMS))


class BaseMainnetChain:
    chain_id = MAINNET_CHAIN_ID
    vm_configuration = MAINNET_VM_CONFIGURATION  # type: Tuple[Tuple[int, Type[BaseVM]], ...]


class MainnetChain(BaseMainnetChain, Chain):
    pass


MAINNET_GENESIS_HEADER = BlockHeader(
    difficulty=eth_constants.GENESIS_DIFFICULTY,
    extra_data=decode_hex("0x11bbe8db4e347b4e8c937c1c8370e4b5ed33adb3db69cbdb7a38e1e50b1b82fa"),
    gas_limit=eth_constants.GENESIS_GAS_LIMIT,
    gas_used=0,
    bloom=0,
    mix_hash=eth_constants.ZERO_HASH32,
    nonce=eth_constants.GENESIS_NONCE,
    block_number=0,
    parent_hash=eth_constants.ZERO_HASH32,
    receipt_root=eth_constants.BLANK_ROOT_HASH,
    uncles_hash=eth_constants.EMPTY_UNCLE_HASH,
    state_root=decode_hex("0xd7f8974fb5ac78d9ac099b9ad5018bedc2ce0a72dad1827a1709da30580f0544"),
    timestamp=0,
    transaction_root=eth_constants.BLANK_ROOT_HASH,
)
