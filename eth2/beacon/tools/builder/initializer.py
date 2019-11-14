from typing import Dict, Sequence, Tuple, Type

from eth.constants import ZERO_HASH32
from eth_typing import BLSPubkey, Hash32
from py_ecc.optimized_bls12_381.optimized_curve import (
    curve_order as BLS12_381_CURVE_ORDER,
)

from eth2._utils.hash import hash_eth2
from eth2.beacon.constants import ZERO_TIMESTAMP
from eth2.beacon.genesis import get_genesis_block, initialize_beacon_state_from_eth1
from eth2.beacon.tools.builder.validator import create_mock_deposit_data
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.deposit_data import DepositData  # noqa: F401
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import Timestamp
from eth2.beacon.validator_status_helpers import activate_validator
from eth2.configs import Eth2Config

from .validator import make_deposit_proof, make_deposit_tree_and_root


def generate_privkey_from_index(index: int) -> int:
    return (
        int.from_bytes(
            hash_eth2(index.to_bytes(length=32, byteorder="little")), byteorder="little"
        )
        % BLS12_381_CURVE_ORDER
    )


def create_mock_deposits_and_root(
    pubkeys: Sequence[BLSPubkey],
    keymap: Dict[BLSPubkey, int],
    config: Eth2Config,
    withdrawal_credentials: Sequence[Hash32] = None,
    leaves: Sequence[Hash32] = None,
) -> Tuple[Tuple[Deposit, ...], Hash32]:
    """
    Creates as many new deposits as there are keys in ``pubkeys``.

    Optionally provide corresponding ``withdrawal_credentials`` to include those.

    Optionally provide the prefix in the sequence of leaves leading up to the
    new deposits made by this function to get the correct updated root. If ``leaves`` is
    empty, this function simulates the genesis deposit tree calculation.
    """
    if not withdrawal_credentials:
        withdrawal_credentials = tuple(
            Hash32(b"\x22" * 32) for _ in range(len(pubkeys))
        )
    else:
        assert len(withdrawal_credentials) == len(pubkeys)
    if not leaves:
        leaves = tuple()

    deposit_datas = tuple()  # type: Tuple[DepositData, ...]
    for key, credentials in zip(pubkeys, withdrawal_credentials):
        privkey = keymap[key]
        deposit_data = create_mock_deposit_data(
            config=config,
            pubkey=key,
            privkey=privkey,
            withdrawal_credentials=credentials,
        )
        deposit_datas += (deposit_data,)

    deposits: Tuple[Deposit, ...] = tuple()
    for index, data in enumerate(deposit_datas):
        deposit_datas_at_count = deposit_datas[: index + 1]
        tree, root = make_deposit_tree_and_root(deposit_datas_at_count)
        proof = make_deposit_proof(deposit_datas_at_count, tree, root, index)

        deposit = Deposit(proof=proof, data=data)
        deposits += (deposit,)

    if len(deposit_datas) > 0:
        return deposits, root
    else:
        return tuple(), ZERO_HASH32


def create_mock_deposit(
    state: BeaconState,
    pubkey: BLSPubkey,
    keymap: Dict[BLSPubkey, int],
    withdrawal_credentials: Hash32,
    config: Eth2Config,
    leaves: Sequence[Hash32] = None,
) -> Tuple[BeaconState, Deposit]:
    deposits, root = create_mock_deposits_and_root(
        (pubkey,),
        keymap,
        config,
        withdrawal_credentials=(withdrawal_credentials,),
        leaves=leaves,
    )
    # sanity check
    assert len(deposits) == 1
    deposit = deposits[0]

    state = state.copy(
        eth1_data=state.eth1_data.copy(
            deposit_root=root,
            deposit_count=state.eth1_data.deposit_count + len(deposits),
        ),
        eth1_deposit_index=0 if not leaves else len(leaves),
    )

    return state, deposit


def create_mock_genesis(
    pubkeys: Sequence[BLSPubkey],
    config: Eth2Config,
    keymap: Dict[BLSPubkey, int],
    genesis_block_class: Type[BaseBeaconBlock],
    genesis_time: Timestamp = ZERO_TIMESTAMP,
) -> Tuple[BeaconState, BaseBeaconBlock]:
    genesis_deposits, deposit_root = create_mock_deposits_and_root(
        pubkeys=pubkeys, keymap=keymap, config=config
    )

    genesis_eth1_data = Eth1Data(
        deposit_root=deposit_root,
        deposit_count=len(genesis_deposits),
        block_hash=ZERO_HASH32,
    )

    state = initialize_beacon_state_from_eth1(
        eth1_block_hash=genesis_eth1_data.block_hash,
        eth1_timestamp=genesis_time,
        deposits=genesis_deposits,
        config=config,
    )

    block = get_genesis_block(
        genesis_state_root=state.hash_tree_root, block_class=genesis_block_class
    )
    assert len(state.validators) == len(pubkeys)

    return state, block


def create_mock_validator(
    pubkey: BLSPubkey,
    config: Eth2Config,
    withdrawal_credentials: Hash32 = ZERO_HASH32,
    is_active: bool = True,
) -> Validator:
    validator = Validator.create_pending_validator(
        pubkey, withdrawal_credentials, config.MAX_EFFECTIVE_BALANCE, config
    )
    if is_active:
        return activate_validator(validator, config.GENESIS_EPOCH)
    else:
        return validator
