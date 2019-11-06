import trio
import pytest
import ssz
import eth_utils
from trio.testing import wait_all_tasks_blocked

from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.constants import DEPOSIT_CONTRACT_TREE_DEPTH
from eth2._utils.merkle.common import verify_merkle_branch
from eth_utils import ValidationError

from trinity.components.eth2.eth1_monitor.eth1_monitor import (
    _make_deposit_tree_and_root,
    GetEth1DataRequest,
    GetEth1DataResponse,
    GetDepositRequest,
    GetDepositResponse,
    Eth1Monitor,
)
from lahja.trio.endpoint import TrioEndpoint


from p2p.trio_service import background_service

from async_generator import asynccontextmanager

import random


from trinity.components.eth2.eth1_monitor.exceptions import Eth1BlockNotFound

from lahja import BroadcastConfig


MIN_DEPOSIT_AMOUNT = 1000000000  # Gwei
FULL_DEPOSIT_AMOUNT = 32000000000  # Gwei

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


@asynccontextmanager
async def Eth1MonitorFactory(
    w3, registration_contract, blocks_delayed_to_query_logs, polling_period, event_bus
):
    m = Eth1Monitor(
        w3,
        registration_contract.address,
        registration_contract.abi,
        blocks_delayed_to_query_logs,
        polling_period,
        event_bus,
    )
    async with background_service(m):
        yield m


# Ref: https://github.com/ethereum/lahja/blob/f0b7ead13298de82c02ed92cfb2d32a8bc00b42a/tests/core/trio/conftest.py  # noqa E501
@asynccontextmanager
async def EventbusFactory():
    async with TrioEndpoint("endpoint-for-testing").run() as client:
        yield client


def test_deploy(w3, registration_contract):
    pass


@pytest.mark.trio
async def test_eth1_monitor_deposit_logs_handling(
    w3,
    registration_contract,
    tester,
    blocks_delayed_to_query_logs,
    polling_period,
    endpoint_server,
):
    amount_0 = deposit(w3, registration_contract)
    amount_1 = deposit(w3, registration_contract)
    async with Eth1MonitorFactory(
        w3,
        registration_contract,
        blocks_delayed_to_query_logs,
        polling_period,
        endpoint_server,
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
    w3,
    registration_contract,
    tester,
    blocks_delayed_to_query_logs,
    polling_period,
    endpoint_server,
):
    async with Eth1MonitorFactory(
        w3,
        registration_contract,
        blocks_delayed_to_query_logs,
        polling_period,
        endpoint_server,
    ) as m:
        # Test: No deposit data available.
        with pytest.raises(ValueError):
            m._get_deposit(deposit_count=1, deposit_index=2)
        deposit_count = 3
        for _ in range(deposit_count):
            deposit(w3, registration_contract)
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


# TODO: Use `clock.autojump.threshold` in trio testing.
# Ref: https://trio.readthedocs.io/en/stable/reference-testing.html#trio.testing.MockClock.autojump_threshold  # noqa: E501
@pytest.mark.trio
async def test_eth1_monitor_get_eth1_data(
    w3,
    registration_contract,
    tester,
    blocks_delayed_to_query_logs,
    polling_period,
    endpoint_server,
):
    async with Eth1MonitorFactory(
        w3,
        registration_contract,
        blocks_delayed_to_query_logs,
        polling_period,
        endpoint_server,
    ) as m:
        tester.mine_blocks(blocks_delayed_to_query_logs)
        # Sleep for a while to wait for mined blocks parsed.
        await trio.sleep(polling_period)
        await wait_all_tasks_blocked()
        cur_block_number = w3.eth.blockNumber
        cur_block_timestamp = w3.eth.getBlock(cur_block_number)["timestamp"]
        # Test: `ValueError` is raised when `distance` where no block is at.
        distance_too_far = cur_block_number + 1
        timestamp_safe = cur_block_timestamp + 1
        with pytest.raises(ValueError):
            m._get_eth1_data(distance_too_far, timestamp_safe)
        # Test: `Eth1BlockNotFound` when there is no block whose timestamp < `timestamp`.
        distance_safe = cur_block_number
        timestamp_genesis = w3.eth.getBlock(0)["timestamp"]
        timestamp_invalid = timestamp_genesis - 1
        with pytest.raises(Eth1BlockNotFound):
            m._get_eth1_data(distance_safe, timestamp_invalid)

        #            `blocks_delayed_to_query_logs`  _latest block
        #                   |-----------------|     /
        # [x] -> [x] -> [ ] -> [ ] -> [ ] -> [ ]
        #  b0     b1     b2     b3     b4     b5

        # Test: `deposit` and mine blocks. Queries with `timestamp` after
        #   `blocks_delayed_to_query_logs` blocks should get the result including the deposit.
        deposit(w3, registration_contract)
        deposit(w3, registration_contract)
        tester.mine_blocks(blocks_delayed_to_query_logs + 1)
        await trio.sleep(polling_period)
        await wait_all_tasks_blocked()
        # `2` is automined blocks by `deposit`,
        # and `blocks_delayed_to_query_logs + 1` are mined later.
        number_recent_blocks = 2 + blocks_delayed_to_query_logs + 1
        current_height = w3.eth.blockNumber
        block_numbers = [
            current_height - i for i in reversed(range(number_recent_blocks))
        ]

        def assert_get_eth1_data(
            block_number,
            distance,
            deposit_count,
            expected_block_number_at_distance=None,
        ):
            block = w3.eth.getBlock(block_number)
            eth1_data = m._get_eth1_data(
                distance=distance, eth1_voting_period_start_timestamp=block["timestamp"]
            )
            assert eth1_data.deposit_count == deposit_count
            if expected_block_number_at_distance is None:
                block_at_distance = w3.eth.getBlock(block_number - distance)
            else:
                block_at_distance = w3.eth.getBlock(expected_block_number_at_distance)
            assert eth1_data.block_hash == block_at_distance["hash"]

        def assert_get_eth1_data_raises(block_number, distance):
            block = w3.eth.getBlock(block_number)
            # `ValidationError` is raised due to `deposit_count == 0` because
            #   `eth1_voting_period_start_timestamp` is earlier than `deposit_included_block`.
            with pytest.raises(ValidationError):
                m._get_eth1_data(
                    distance=distance,
                    eth1_voting_period_start_timestamp=block["timestamp"],
                )

        # Assert b0
        assert_get_eth1_data(block_numbers[0], 0, 1)
        assert_get_eth1_data_raises(block_numbers[0], 1)

        # Assert b1
        assert_get_eth1_data(block_numbers[1], 0, 2)
        assert_get_eth1_data(block_numbers[1], 1, 1)
        assert_get_eth1_data_raises(block_numbers[1], 2)

        # Assert b2
        assert_get_eth1_data(block_numbers[2], 0, 2)
        assert_get_eth1_data(block_numbers[2], 1, 2)
        assert_get_eth1_data(block_numbers[2], 2, 1)
        assert_get_eth1_data_raises(block_numbers[2], 3)

        # Assert b3, b4, b5.
        # Since these blocks are still within `blocks_delayed_to_query_logs`,
        # queries with their timestamps should get the result of the latest block after
        # `blocks_delayed_to_query_logs` blocks.
        assert_get_eth1_data(
            block_numbers[3], 0, 2, expected_block_number_at_distance=block_numbers[2]
        )
        assert_get_eth1_data(
            block_numbers[4], 0, 2, expected_block_number_at_distance=block_numbers[2]
        )
        assert_get_eth1_data(
            block_numbers[5], 0, 2, expected_block_number_at_distance=block_numbers[2]
        )


# @pytest.mark.trio
# async def test_eth1_monitor_haha(
#     w3,
#     registration_contract,
#     tester,
#     blocks_delayed_to_query_logs,
#     polling_period,
#     endpoint_server,
#     endpoint_client,
# ):
#     # async with EventbusFactory() as event_bus:
#     async with Eth1MonitorFactory(
#         w3,
#         registration_contract,
#         blocks_delayed_to_query_logs,
#         polling_period,
#         endpoint_server,
#     ) as m:
#         deposit(w3, registration_contract)
#         tester.mine_blocks(blocks_delayed_to_query_logs)
#         await trio.sleep(polling_period)
#         await wait_all_tasks_blocked()

#         broadcast_config = BroadcastConfig(internal=True)

#         async def stream_response():
#             print("!@# stream_response")
#             await endpoint_client.wait_until_any_endpoint_subscribed_to(
#                 GetDepositRequest
#             )
#             print("!@# someone is subscribed to `GetDepositRequest`")
#             resp = await endpoint_client.request(
#                 GetDepositRequest(deposit_count=1, deposit_index=0), broadcast_config
#             )
#             print(f"!@# stream_response={resp}")

#         await stream_response()
#     # nursery.start_soon(
#     #     event_bus.broadcast,
#     #     GetDepositRequest(deposit_count=1, deposit_index=0),
#     #     broadcast_config,
#     # )
