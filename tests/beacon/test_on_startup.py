from eth.constants import (
    ZERO_HASH32,
)

from eth.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth.beacon.enums import (
    SignatureDomain,
)
from eth.beacon.helpers import (
    get_domain,
)
from eth.beacon.types.deposits import Deposit
from eth.beacon.types.deposit_data import DepositData
from eth.beacon.types.deposit_input import DepositInput
from eth.beacon.types.fork_data import ForkData

from eth.beacon.on_startup import (
    get_genesis_block,
    get_initial_beacon_state,
)

from tests.beacon.helpers import (
    make_deposit_input,
    sign_proof_of_possession,
)


def test_get_genesis_block():
    startup_state_root = b'\x10' * 32
    initial_slot_number = 10
    genesis_block = get_genesis_block(startup_state_root, initial_slot_number)
    assert genesis_block.slot == initial_slot_number
    assert genesis_block.parent_root == ZERO_HASH32
    assert genesis_block.state_root == startup_state_root
    assert genesis_block.randao_reveal == ZERO_HASH32
    assert genesis_block.candidate_pow_receipt_root == ZERO_HASH32
    assert genesis_block.signature == EMPTY_SIGNATURE
    assert genesis_block.body.is_empty


def test_get_initial_beacon_state(
        privkeys,
        pubkeys,
        initial_slot_number,
        initial_fork_version,
        shard_count,
        latest_block_roots_length,
        epoch_length,
        target_committee_size,
        max_deposit,
        zero_balance_validator_ttl,
        collective_penalty_calculation_period,
        whistleblower_reward_quotient):
    withdrawal_credentials = b'\x22' * 32
    randao_commitment = b'\x33' * 32
    fork_data = ForkData(
        pre_fork_version=initial_fork_version,
        post_fork_version=initial_fork_version,
        fork_slot=initial_slot_number,
    )
    domain = get_domain(
        fork_data,
        initial_slot_number,
        SignatureDomain.DOMAIN_DEPOSIT,
    )
    validator_count = 10

    initial_validator_deposits = (
        Deposit(
            merkle_branch=(
                b'\x11' * 32
                for j in range(10)
            ),
            merkle_tree_index=i,
            deposit_data=DepositData(
                deposit_input=DepositInput(
                    pubkey=pubkeys[i],
                    withdrawal_credentials=withdrawal_credentials,
                    randao_commitment=randao_commitment,
                    proof_of_possession=sign_proof_of_possession(
                        deposit_input=make_deposit_input(
                            pubkey=pubkeys[i],
                            withdrawal_credentials=withdrawal_credentials,
                            randao_commitment=randao_commitment,
                        ),
                        privkey=privkeys[i],
                        domain=domain,
                    ),
                ),
                value=max_deposit,
                timestamp=0,
            ),
        )
        for i in range(validator_count)
    )
    genesis_time = 10
    processed_pow_receipt_root = b'\x10' * 32

    state = get_initial_beacon_state(
        initial_validator_deposits=initial_validator_deposits,
        genesis_time=genesis_time,
        processed_pow_receipt_root=processed_pow_receipt_root,
        initial_slot_number=initial_slot_number,
        initial_fork_version=initial_fork_version,
        shard_count=shard_count,
        latest_block_roots_length=latest_block_roots_length,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        max_deposit=max_deposit,
        zero_balance_validator_ttl=zero_balance_validator_ttl,
        collective_penalty_calculation_period=collective_penalty_calculation_period,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
    )

    assert state.slot == initial_slot_number
    assert len(state.validator_registry) == validator_count
