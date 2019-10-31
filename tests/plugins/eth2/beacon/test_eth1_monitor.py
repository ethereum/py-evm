import trio
import pytest
import ssz
import eth_utils
from trio.testing import wait_all_tasks_blocked

from eth2.beacon.types.deposit_data import DepositData
from eth2._utils.merkle.sparse import calc_merkle_tree_from_leaves, get_root
from eth2._utils.merkle.common import get_merkle_proof, verify_merkle_branch
from eth2._utils.hash import hash_eth2
from eth2.beacon.constants import DEPOSIT_CONTRACT_TREE_DEPTH

from trinity.plugins.eth2.beacon.eth1_monitor import (
    Eth1Monitor,
    _make_deposit_tree_and_root,
)

from p2p.trio_service import background_service

import random

from .constants import MIN_DEPOSIT_AMOUNT, FULL_DEPOSIT_AMOUNT
from .factories import Eth1MonitorFactory


SAMPLE_PUBKEY = b"\x11" * 48
SAMPLE_WITHDRAWAL_CREDENTIALS = b"\x22" * 32
SAMPLE_VALID_SIGNATURE = b"\x33" * 96


def get_random_valid_deposit_amount() -> int:
    return random.randint(MIN_DEPOSIT_AMOUNT, FULL_DEPOSIT_AMOUNT)


def deposit(w3, registration_contract) -> int:
    amount = get_random_valid_deposit_amount()
    deposit_input = (
        SAMPLE_PUBKEY,
        SAMPLE_WITHDRAWAL_CREDENTIALS,
        SAMPLE_VALID_SIGNATURE,
        ssz.get_hash_tree_root(
            DepositData(
                pubkey=SAMPLE_PUBKEY,
                withdrawal_credentials=SAMPLE_WITHDRAWAL_CREDENTIALS,
                amount=amount,
                signature=SAMPLE_VALID_SIGNATURE,
            )
        ),
    )
    tx_hash = registration_contract.functions.deposit(*deposit_input).transact(
        {"value": amount * eth_utils.denoms.gwei}
    )
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
    assert tx_receipt["status"]
    return amount


def test_deploy(w3, registration_contract):
    pass


@pytest.mark.trio
async def test_eth1_monitor_deposit_logs_handling(
    w3, registration_contract, tester, blocks_delayed_to_query_logs, polling_period
):
    amount_0 = deposit(w3, registration_contract)
    amount_1 = deposit(w3, registration_contract)
    async with Eth1MonitorFactory(
        w3, registration_contract, blocks_delayed_to_query_logs, polling_period
    ) as m:
        # Test: previous logs can still be queried after `Eth1Monitor` is run.
        await wait_all_tasks_blocked()
        assert len(m._deposit_data) == 0
        assert len(m._block_number_to_hash) == 0
        #       `blocks_delayed_to_query_logs`
        #            |-----------------|
        # [x] -> [x] -> [ ] -> [ ] -> [ ]
        tester.mine_blocks(blocks_delayed_to_query_logs - 1)
        await trio.sleep(polling_period)
        await wait_all_tasks_blocked()
        assert len(m._deposit_data) == 1 and m._deposit_data[0].amount == amount_0
        tester.mine_blocks(1)
        await trio.sleep(polling_period)
        await wait_all_tasks_blocked()
        assert len(m._deposit_data) == 2 and m._deposit_data[1].amount == amount_1
        # Test: a new log can be queried after the transaction is included in a block
        #   and `blocks_delayed_to_query_logs` blocks are mined.
        #   `blocks_delayed_to_query_logs`
        #     |-----------------|
        # [x] -> [ ] -> [ ] -> [ ]
        amount_2 = deposit(w3, registration_contract)
        tester.mine_blocks(blocks_delayed_to_query_logs)
        await trio.sleep(polling_period)
        await wait_all_tasks_blocked()
        assert len(m._deposit_data) == 3 and m._deposit_data[2].amount == amount_2


@pytest.mark.trio
async def test_eth1_monitor_get_deposit(
    w3, registration_contract, tester, blocks_delayed_to_query_logs, polling_period
):
    async with Eth1MonitorFactory(
        w3, registration_contract, blocks_delayed_to_query_logs, polling_period
    ) as m:
        # Test: No deposit data available.
        with pytest.raises(ValueError):
            m._get_deposit(deposit_count=1, deposit_index=2)
        deposit_count = 3
        list_deposit_amount = [
            deposit(w3, registration_contract) for _ in range(deposit_count)
        ]
        #          `blocks_delayed_to_query_logs`
        #            |-----------------|
        # [x] -> [x] -> [x] -> [ ] -> [ ]
        tester.mine_blocks(blocks_delayed_to_query_logs - 1)
        await trio.sleep(polling_period)
        await wait_all_tasks_blocked()
        # Test: The last deposit hasn't been put in `Eth1Monitor._deposit_data`.
        #   Thus, it fails when we query with `deposit_count>=deposit_count` or
        #   `deposit_index>=deposit_count-1`.
        with pytest.raises(ValueError):
            m._get_deposit(deposit_count=deposit_count, deposit_index=0)
        with pytest.raises(ValueError):
            m._get_deposit(
                deposit_count=deposit_count - 1, deposit_index=deposit_count - 1
            )

        def verify_deposit(deposit_count, deposit_index, eth1_monitor) -> bool:
            deposit = eth1_monitor._get_deposit(
                deposit_count=deposit_count, deposit_index=deposit_index
            )
            _, root = _make_deposit_tree_and_root(
                eth1_monitor._deposit_data[:deposit_count]
            )
            return verify_merkle_branch(
                deposit.data.hash_tree_root,
                deposit.proof,
                DEPOSIT_CONTRACT_TREE_DEPTH + 1,
                deposit_index,
                root,
            )

        for _deposit_count in (deposit_count - 1, deposit_count - 2):
            assert verify_deposit(
                deposit_count=_deposit_count,
                deposit_index=deposit_count - 3,
                eth1_monitor=m,
            )
        # Test: `deposit_index` should be less than `deposit_count`
        with pytest.raises(ValueError):
            m._get_deposit(deposit_count=1, deposit_index=1)


@pytest.mark.trio
async def test_eth1_monitor_get_eth1_data(
    w3, registration_contract, tester, blocks_delayed_to_query_logs, polling_period
):
    async with Eth1MonitorFactory(
        w3, registration_contract, blocks_delayed_to_query_logs, polling_period
    ) as m:
        # Test: `distance` where no block is at.
        with pytest.raises(ValueError):
            m._get_eth1_data(1)
        # TODO: More tests
