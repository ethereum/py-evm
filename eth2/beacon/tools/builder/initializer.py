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

from eth2._utils.merkle.common import (
    get_merkle_proof,
)
from eth2._utils.merkle.sparse import (
    calc_merkle_tree_from_leaves,
    get_merkle_root,
)
from eth2.configs import Eth2Config
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.constants import (
    ZERO_TIMESTAMP,
)
from eth2.beacon.on_genesis import (
    get_genesis_block,
    get_genesis_beacon_state,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.deposit_data import DepositData  # noqa: F401
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Timestamp,
    ValidatorIndex,
)

from eth2.beacon.tools.builder.validator import (
    create_mock_deposit_data,
)


def create_mock_genesis_validator_deposits_and_root(
        num_validators: int,
        config: Eth2Config,
        pubkeys: Sequence[BLSPubkey],
        keymap: Dict[BLSPubkey, int]) -> Tuple[Tuple[Deposit, ...], Hash32]:
    # Mock data
    withdrawal_credentials = Hash32(b'\x22' * 32)
    fork = Fork(
        previous_version=config.GENESIS_FORK_VERSION.to_bytes(4, 'little'),
        current_version=config.GENESIS_FORK_VERSION.to_bytes(4, 'little'),
        epoch=config.GENESIS_EPOCH,
    )

    deposit_data_array = tuple()  # type: Tuple[DepositData, ...]
    deposit_data_leaves = tuple()  # type: Tuple[Hash32, ...]

    for i in range(num_validators):
        deposit_data = create_mock_deposit_data(
            config=config,
            pubkeys=pubkeys,
            keymap=keymap,
            validator_index=ValidatorIndex(i),
            withdrawal_credentials=withdrawal_credentials,
            fork=fork,
        )
        item = hash_eth2(ssz.encode(deposit_data))
        deposit_data_leaves += (item,)
        deposit_data_array += (deposit_data,)

    tree = calc_merkle_tree_from_leaves(deposit_data_leaves)
    root = get_merkle_root(deposit_data_leaves)

    genesis_validator_deposits = tuple(
        Deposit(
            proof=get_merkle_proof(tree, item_index=i),
            index=i,
            deposit_data=deposit_data_array[i],
        )
        for i in range(num_validators)
    )

    return genesis_validator_deposits, root


def create_mock_genesis(
        num_validators: int,
        config: Eth2Config,
        keymap: Dict[BLSPubkey, int],
        genesis_block_class: Type[BaseBeaconBlock],
        genesis_time: Timestamp=ZERO_TIMESTAMP) -> Tuple[BeaconState, BaseBeaconBlock]:
    assert num_validators <= len(keymap)

    pubkeys = list(keymap)[:num_validators]

    genesis_validator_deposits, deposit_root = create_mock_genesis_validator_deposits_and_root(
        num_validators=num_validators,
        config=config,
        pubkeys=pubkeys,
        keymap=keymap,
    )

    genesis_eth1_data = Eth1Data(
        deposit_root=deposit_root,
        block_hash=ZERO_HASH32,
    )

    state = get_genesis_beacon_state(
        genesis_validator_deposits=genesis_validator_deposits,
        genesis_time=genesis_time,
        genesis_eth1_data=genesis_eth1_data,
        genesis_slot=config.GENESIS_SLOT,
        genesis_epoch=config.GENESIS_EPOCH,
        genesis_fork_version=config.GENESIS_FORK_VERSION,
        genesis_start_shard=config.GENESIS_START_SHARD,
        shard_count=config.SHARD_COUNT,
        min_seed_lookahead=config.MIN_SEED_LOOKAHEAD,
        slots_per_historical_root=config.SLOTS_PER_HISTORICAL_ROOT,
        latest_active_index_roots_length=config.LATEST_ACTIVE_INDEX_ROOTS_LENGTH,
        slots_per_epoch=config.SLOTS_PER_EPOCH,
        max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
        latest_slashed_exit_length=config.LATEST_SLASHED_EXIT_LENGTH,
        latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
        activation_exit_delay=config.ACTIVATION_EXIT_DELAY,
        deposit_contract_tree_depth=config.DEPOSIT_CONTRACT_TREE_DEPTH,
        block_class=genesis_block_class,
    )

    block = get_genesis_block(
        genesis_state_root=state.root,
        genesis_slot=config.GENESIS_SLOT,
        block_class=genesis_block_class,
    )
    assert len(state.validator_registry) == num_validators

    return state, block
