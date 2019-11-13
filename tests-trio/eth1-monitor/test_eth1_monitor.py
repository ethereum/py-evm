from eth_utils import ValidationError
from lahja import BroadcastConfig
import pytest

import trio
from trio.testing import wait_all_tasks_blocked

from eth2.beacon.constants import DEPOSIT_CONTRACT_TREE_DEPTH
from eth2._utils.merkle.common import verify_merkle_branch
from p2p.trio_service import background_service
from trinity.components.eth2.eth1_monitor.eth1_monitor import (
    make_deposit_tree_and_root,
    GetEth1DataRequest,
    GetDepositRequest,
    Eth1Monitor,
)
from trinity.components.eth2.eth1_monitor.exceptions import (
    DepositDataCorrupted,
    Eth1BlockNotFound,
    Eth1MonitorValidationError,
)


@pytest.mark.trio
async def test_logs_handling(
    w3,
    deposit_contract,
    tester,
    num_blocks_confirmed,
    polling_period,
    start_block_number,
    endpoint_server,
    func_do_deposit,
):
    amount_0 = func_do_deposit()
    amount_1 = func_do_deposit()
    m = Eth1Monitor(
        w3=w3,
        deposit_contract_address=deposit_contract.address,
        deposit_contract_abi=deposit_contract.abi,
        num_blocks_confirmed=num_blocks_confirmed,
        polling_period=polling_period,
        start_block_number=start_block_number,
        event_bus=endpoint_server,
    )
    async with background_service(m):
        # Test: logs emitted prior to starting `Eth1Monitor` can still be queried.
        await wait_all_tasks_blocked()
        assert len(m._deposit_data) == 0

        tester.mine_blocks(num_blocks_confirmed - 1)
        # Test: only single deposit is processed.
        #      `num_blocks_confirmed`
        #       |-----------------|
        # [x] -> [x] -> [ ] -> [ ]
        await trio.sleep(polling_period)
        await wait_all_tasks_blocked()
        assert len(m._deposit_data) == 1 and m._deposit_data[0].amount == amount_0

        tester.mine_blocks(1)
        # Test: both deposits are processed.
        #             `num_blocks_confirmed`
        #              |-----------------|
        # [x] -> [x] -> [ ] -> [ ] -> [ ]
        await trio.sleep(polling_period)
        await wait_all_tasks_blocked()
        assert len(m._deposit_data) == 2 and m._deposit_data[1].amount == amount_1
        # Test: a new log can be queried after the transaction is included in a block
        #   and `num_blocks_confirmed` blocks are mined.
        #                                         `num_blocks_confirmed`
        #                                          |-----------------|
        # [x] -> [x] -> [ ] -> [ ] -> [ ] -> [x] -> [ ] -> [ ] -> [ ]
        amount_2 = func_do_deposit()
        tester.mine_blocks(num_blocks_confirmed)
        await trio.sleep(polling_period)
        await wait_all_tasks_blocked()
        assert len(m._deposit_data) == 3 and m._deposit_data[2].amount == amount_2


@pytest.mark.trio
async def test_get_deposit(
    w3, tester, num_blocks_confirmed, polling_period, eth1_monitor, func_do_deposit
):
    # Test: No deposit data available.
    with pytest.raises(Eth1MonitorValidationError):
        eth1_monitor._get_deposit(deposit_count=1, deposit_index=2)
    num_deposits = 3
    for _ in range(num_deposits):
        func_do_deposit()
    #             `num_blocks_confirmed`
    #              |-----------------|
    # [x] -> [x] -> [x] -> [ ] -> [ ]
    tester.mine_blocks(num_blocks_confirmed - 1)
    await trio.sleep(polling_period)
    await wait_all_tasks_blocked()
    # Test: The last deposit hasn't been put in `Eth1Monitor._deposit_data`.
    #   Thus, it fails when we query with `deposit_count>=deposit_count` or
    #   `deposit_index>=deposit_count-1`.
    with pytest.raises(Eth1MonitorValidationError):
        eth1_monitor._get_deposit(deposit_count=num_deposits, deposit_index=0)
    with pytest.raises(Eth1MonitorValidationError):
        eth1_monitor._get_deposit(
            deposit_count=num_deposits - 1, deposit_index=num_deposits - 1
        )

    def verify_deposit(deposit_count, deposit_index, eth1_monitor) -> bool:
        deposit = eth1_monitor._get_deposit(
            deposit_count=deposit_count, deposit_index=deposit_index
        )
        _, root = make_deposit_tree_and_root(eth1_monitor._deposit_data[:deposit_count])
        return verify_merkle_branch(
            deposit.data.hash_tree_root,
            deposit.proof,
            DEPOSIT_CONTRACT_TREE_DEPTH + 1,
            deposit_index,
            root,
        )

    for count in (num_deposits - 1, num_deposits - 2):
        assert verify_deposit(
            deposit_count=count, deposit_index=0, eth1_monitor=eth1_monitor
        )


# TODO: Use `clock.autojump.threshold` in trio testing.
# Ref: https://trio.readthedocs.io/en/stable/reference-testing.html#trio.testing.MockClock.autojump_threshold  # noqa: E501
@pytest.mark.trio
async def test_get_eth1_data(
    w3,
    tester,
    num_blocks_confirmed,
    polling_period,
    eth1_monitor,
    func_do_deposit,
    monkeypatch,
):
    tester.mine_blocks(num_blocks_confirmed)
    # Sleep for a while to wait for mined blocks parsed.
    await trio.sleep(polling_period)
    await wait_all_tasks_blocked()
    cur_block_number = w3.eth.blockNumber
    cur_block_timestamp = w3.eth.getBlock(cur_block_number)["timestamp"]
    # Test: `Eth1MonitorValidationError` is raised when `distance` where no block is at.
    distance_invalid = cur_block_number + 1
    timestamp_safe = cur_block_timestamp + 1
    with pytest.raises(Eth1MonitorValidationError):
        eth1_monitor._get_eth1_data(distance_invalid, timestamp_safe)
    # Test: `Eth1BlockNotFound` when there is no block whose timestamp < `timestamp`.
    distance_safe = cur_block_number
    timestamp_genesis = w3.eth.getBlock(0)["timestamp"]
    timestamp_invalid = timestamp_genesis - 1
    with pytest.raises(Eth1BlockNotFound):
        eth1_monitor._get_eth1_data(distance_safe, timestamp_invalid)

    #                    `num_blocks_confirmed`
    #                     |-----------------|
    # [x] -> [x] -> [ ] -> [ ] -> [ ] -> [ ]  <- latest block
    #  b0     b1     b2     b3     b4     b5

    # Test: `deposit` and mine blocks. Queries with `timestamp` after
    #   `num_blocks_confirmed` blocks should get the result including the deposit.
    func_do_deposit()
    func_do_deposit()
    tester.mine_blocks(num_blocks_confirmed + 1)
    await trio.sleep(polling_period)
    await wait_all_tasks_blocked()
    # `2` is automined blocks by `deposit`,
    # and `num_blocks_confirmed + 1` are mined later.
    number_recent_blocks = 2 + num_blocks_confirmed + 1
    current_height = w3.eth.blockNumber
    block_numbers = list(
        range(current_height - number_recent_blocks + 1, current_height + 1)
    )

    def assert_get_eth1_data(
        block_number, distance, deposit_count, expected_block_number_at_distance=None
    ):
        block = w3.eth.getBlock(block_number)
        eth1_data = eth1_monitor._get_eth1_data(
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
        # Assert `ValidationError` is raised due to `deposit_count == 0`, if
        # `eth1_voting_period_start_timestamp` is earlier than the timestamps of all blocks
        # which contain deposits.
        with pytest.raises(ValidationError):
            eth1_monitor._get_eth1_data(
                distance=distance, eth1_voting_period_start_timestamp=block["timestamp"]
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
    # Since these blocks are still within `num_blocks_confirmed`,
    # queries with `distance == 0` will return eth1_data at b2.
    # `num_blocks_confirmed` blocks.
    assert_get_eth1_data(
        block_numbers[3], 0, 2, expected_block_number_at_distance=block_numbers[2]
    )
    assert_get_eth1_data(
        block_numbers[4], 0, 2, expected_block_number_at_distance=block_numbers[2]
    )
    assert_get_eth1_data(
        block_numbers[5], 0, 2, expected_block_number_at_distance=block_numbers[2]
    )

    # Test: `DepositDataCorrupted` is raised when the calculated `deposit_root` from
    #   `deposit_data` mismatches the one got from the deposit contract.
    mismatched_deposit_data = eth1_monitor._deposit_data[1:]
    with monkeypatch.context() as m_context:
        m_context.setattr(eth1_monitor, "_deposit_data", mismatched_deposit_data)
        with pytest.raises(DepositDataCorrupted):
            eth1_monitor._get_eth1_data(
                distance=0,
                eth1_voting_period_start_timestamp=w3.eth.getBlock(current_height)[
                    "timestamp"
                ],
            )


@pytest.mark.trio
async def test_ipc(
    w3,
    tester,
    num_blocks_confirmed,
    polling_period,
    endpoint_server,
    endpoint_client,
    eth1_monitor,
    func_do_deposit,
):
    func_do_deposit()
    tester.mine_blocks(num_blocks_confirmed)
    await trio.sleep(polling_period)
    await wait_all_tasks_blocked()

    broadcast_config = BroadcastConfig(endpoint_server.name)

    async def request(request_type, **kwargs):
        await endpoint_client.wait_until_any_endpoint_subscribed_to(request_type)
        resp = await endpoint_client.request(request_type(**kwargs), broadcast_config)
        return resp.to_data()

    # Result from IPC should be the same as the direct call with the same args.

    # Test: `get_deposit`
    # Succeeds
    get_deposit_kwargs = {"deposit_count": 1, "deposit_index": 0}
    assert eth1_monitor._get_deposit(**get_deposit_kwargs) == (
        await request(GetDepositRequest, **get_deposit_kwargs)
    )
    # Fails
    get_deposit_fails_kwargs = {"deposit_count": 0, "deposit_index": 0}
    with pytest.raises(Eth1MonitorValidationError):
        await request(GetDepositRequest, **get_deposit_fails_kwargs)

    # Test: `get_eth1_data`
    get_eth1_data_kwargs = {
        "distance": 0,
        "eth1_voting_period_start_timestamp": w3.eth.getBlock("latest")["timestamp"],
    }
    # Succeeds
    assert eth1_monitor._get_eth1_data(**get_eth1_data_kwargs) == (
        await request(GetEth1DataRequest, **get_eth1_data_kwargs)
    )
    # Fails
    get_eth1_data_kwargs_fails = {
        "distance": 1,
        "eth1_voting_period_start_timestamp": w3.eth.getBlock("latest")["timestamp"],
    }
    with pytest.raises(Eth1MonitorValidationError):
        await request(GetEth1DataRequest, **get_eth1_data_kwargs_fails)
