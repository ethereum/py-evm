from collections import defaultdict
from typing import Any, NamedTuple, List, Dict

import trio

import web3

from p2p.trio_service import Service

from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.eth1_data import Eth1Data

from .exceptions import InvalidLog


# https://github.com/ethereum/eth2.0-specs/blob/61f2a0662ebcfb4c097360cc1835c5f01872705c/configs/mainnet.yaml#L65  # noqa: E501
SLOTS_PER_ETH1_VOTING_PERIOD = 1024


# https://github.com/ethereum/eth2.0-specs/blob/dev/deposit_contract/contracts/validator_registration.v.py#L10-L16  # noqa: E501
class DepositEvent(NamedTuple):
    pass


class Eth1Monitor(Service):
    _w3: web3.Web3
    _log_filter: Any  # FIXME: change to the correct type.
    # TODO: Change to broadcast with lahja: Others can request and get the response.
    _deposit_data: List[Any]
    _block_hash_to_number: Dict[bytes, int]
    _block_number_to_deposit_count: Dict[int, int]
    _highest_log_block_number: int

    def __init__(
        self,
        w3: web3.Web3,
        contract_address: bytes,
        contract_abi: str,
        blocks_delayed_to_query_logs: int,
    ) -> None:
        self._w3 = w3
        self._deposit_contract = w3.eth.contract(
            address=contract_address, abi=contract_abi
        )
        self._block_filter = self._w3.eth.filter("latest")
        self._blocks_delayed_to_query_logs = blocks_delayed_to_query_logs
        self._deposit_data = []
        self._block_hash_to_number = {}
        self._block_number_to_deposit_count = defaultdict(lambda: 0)
        self._highest_log_block_number = 0

    async def run(self) -> None:
        send_channel, receive_channel = trio.open_memory_channel(0)
        self.manager.run_daemon_task(self._poll_new_logs, send_channel)
        self.manager.run_daemon_task(self._handle_new_logs, receive_channel)
        await self.manager.wait_stopped()

    def _get_logs(self, from_block: int, to_block: int):
        # NOTE: web3 v4 does not support `events.Event.getLogs`.
        # We should change the install-and-uninstall pattern to it after we update to v5.
        log_filter = self._deposit_contract.events.DepositEvent.createFilter(
            fromBlock=from_block, toBlock=to_block
        )
        logs = log_filter.get_new_entries()
        self._w3.eth.uninstallFilter(log_filter.filter_id)
        return logs

    async def _poll_new_logs(self, send_channel) -> None:
        async with send_channel:
            while True:
                for blockhash in self._block_filter.get_new_entries():
                    block_number = self._w3.eth.getBlock(blockhash)["number"]
                    lookback_block_number = (
                        block_number - self._blocks_delayed_to_query_logs
                    )
                    if lookback_block_number < 0:
                        continue
                    logs = self._get_logs(lookback_block_number, lookback_block_number)
                    for log in logs:
                        await send_channel.send(log)
                await trio.sleep(0.1)

    def _process_log(self, log) -> None:
        # TODO:
        #   1. Get the `blockhash` from each log and map `blockhash` to `deposit_count`.
        #   2. Assert `block_number >= # of list elements`
        block_hash = log["blockHash"]
        block_number = log["blockNumber"]
        if block_number < self._highest_log_block_number:
            raise InvalidLog(
                f"Received a log from a non-head block. There must have been an re-org. log={log}"
            )
        if block_hash not in self._block_hash_to_number:
            self._block_hash_to_number[block_hash] = block_number
        # TODO: These can be possibly optimized with accumulated `deposit_count`
        #   for each `block_number`. However, it requires `_block_number_to_deposit_count`
        #   to be a list or OrderDict?
        self._block_number_to_deposit_count[block_number] += 1
        self._deposit_data.append(log)
        if block_number > self._highest_log_block_number:
            self._highest_log_block_number = block_number

    async def _handle_new_logs(self, receive_channel) -> None:
        async with receive_channel:
            async for log in receive_channel:
                self._process_log(log)

    async def _get_deposit(self, deposit_index: int, deposit_count: int) -> Deposit:
        # Returns `Deposit`
        pass

    # https://github.com/ethereum/eth2.0-specs/blob/61f2a0662ebcfb4c097360cc1835c5f01872705c/specs/validator/0_beacon-chain-validator.md#eth1-data  # noqa: E501
    async def _get_eth1_data(self, distance: int) -> Eth1Data:
        # TODO:
        #   1. `Eth1Data.block_hash` = `block_hash` of the block with the
        #       height `{height of canonical head} - {distance}`.
        #   2. `Eth1Data.deposit_count`: get the corresponding `deposit_count` to the block
        #       from step (1).
        #   3. Compute deposit tree with `deposit_count` deposits.
        #   4. `Eth1Data.deposit_root`: the root of deposit tree from step (3).

        pass
