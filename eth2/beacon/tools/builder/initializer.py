from typing import (
    Dict,
    Sequence,
    Tuple,
    Type,
)

from eth_typing import (
    BLSPubkey,
    Hash32,
)
import ssz

from eth.constants import (
    ZERO_HASH32,
)

from eth2._utils.hash import (
    hash_eth2,
)
from eth2._utils.merkle.common import (
    get_merkle_proof,
)
from eth2._utils.merkle.sparse import (
    calc_merkle_tree_from_leaves,
    get_merkle_root,
)
from eth2.configs import Eth2Config
from eth2.beacon.constants import (
    ZERO_TIMESTAMP,
)
from eth2.beacon.genesis import (
    get_genesis_block,
    get_genesis_beacon_state,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.deposit_data import DepositData  # noqa: F401
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import (
    Timestamp,
    ValidatorIndex,
)
from eth2.beacon.validator_status_helpers import (
    activate_validator,
)

from eth2.beacon.tools.builder.validator import (
    create_mock_deposit_data,
)


def create_mock_genesis_validator_deposits_and_root(
        validator_count: int,
        config: Eth2Config,
        pubkeys: Sequence[BLSPubkey],
        keymap: Dict[BLSPubkey, int]) -> Tuple[Tuple[Deposit, ...], Hash32]:
    # Mock data
    withdrawal_credentials = Hash32(b'\x22' * 32)

    deposit_data_array = tuple()  # type: Tuple[DepositData, ...]
    deposit_data_leaves = tuple()  # type: Tuple[Hash32, ...]

    for i in range(validator_count):
        privkey = keymap[pubkeys[ValidatorIndex(i)]]
        deposit_data = create_mock_deposit_data(
            config=config,
            pubkey=pubkeys[ValidatorIndex(i)],
            privkey=privkey,
            withdrawal_credentials=withdrawal_credentials,
        )
        item = hash_eth2(ssz.encode(deposit_data))
        deposit_data_leaves += (item,)
        deposit_data_array += (deposit_data,)

    tree = calc_merkle_tree_from_leaves(deposit_data_leaves)
    root = get_merkle_root(deposit_data_leaves)

    genesis_validator_deposits = tuple(
        Deposit(
            proof=get_merkle_proof(tree, item_index=i),
            data=deposit_data_array[i],
        )
        for i in range(validator_count)
    )

    return genesis_deposits, root


def create_mock_genesis(
        num_validators: int,
        config: Eth2Config,
        keymap: Dict[BLSPubkey, int],
        genesis_block_class: Type[BaseBeaconBlock],
        genesis_time: Timestamp=ZERO_TIMESTAMP) -> Tuple[BeaconState, BaseBeaconBlock]:
    assert num_validators <= len(keymap)

    pubkeys = list(keymap)[:num_validators]

    genesis_deposits, deposit_root = create_mock_genesis_validator_deposits_and_root(
        num_validators=num_validators,
        config=config,
        pubkeys=pubkeys,
        keymap=keymap,
    )

    genesis_eth1_data = Eth1Data(
        deposit_root=deposit_root,
        deposit_count=len(genesis_deposits),
        block_hash=ZERO_HASH32,
    )

    state = get_genesis_beacon_state(
        genesis_deposits=genesis_deposits,
        genesis_time=genesis_time,
        genesis_eth1_data=genesis_eth1_data,
        config=config,
    )

    block = get_genesis_block(
        genesis_state_root=state.root,
        block_class=genesis_block_class,
    )
    assert len(state.validators) == num_validators

    return state, block


def mock_validator(pubkey: BLSPubkey,
                   config: Eth2Config,
                   withdrawal_credentials: Hash32=ZERO_HASH32,
                   is_active: bool=True) -> Validator:
    validator = Validator.create_pending_validator(
        pubkey,
        withdrawal_credentials,
        config.MAX_EFFECTIVE_BALANCE,
        config,
    )
    if is_active:
        return activate_validator(
            validator,
            config.GENESIS_EPOCH,
        )
    else:
        return validator
