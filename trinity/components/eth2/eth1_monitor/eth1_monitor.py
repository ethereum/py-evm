from dataclasses import dataclass
from collections import OrderedDict
from typing import Any, NamedTuple, List, Dict, Tuple, Sequence

import trio

import web3

from p2p.trio_service import Service

from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.eth1_data import Eth1Data
from eth2._utils.merkle.sparse import calc_merkle_tree_from_leaves, get_root
from eth2._utils.merkle.common import MerkleTree, get_merkle_proof
from eth_typing import Hash32
from eth2._utils.hash import hash_eth2
from eth2.beacon.typing import Timestamp
from eth_utils import ValidationError

from .exceptions import InvalidEth1Log, Eth1Forked, Eth1BlockNotFound

from lahja import (
    BaseEvent,
    TrioEndpoint,
    ConnectionConfig,
    BroadcastConfig,
    EndpointAPI,
)


ETH1_MONITOR_LAHJA_CONFIG = ConnectionConfig.from_name("eth1_monitor")


# TODO: Refactoring


def _make_deposit_tree_and_root(
    list_deposit_data: Sequence[DepositData]
) -> Tuple[MerkleTree, Hash32]:
    deposit_data_leaves = [data.hash_tree_root for data in list_deposit_data]
    length_mix_in = len(list_deposit_data).to_bytes(32, byteorder="little")
    tree = calc_merkle_tree_from_leaves(deposit_data_leaves)
    tree_root = get_root(tree)
    tree_root_with_mix_in = hash_eth2(tree_root + length_mix_in)
    return tree, tree_root_with_mix_in


def _make_deposit_proof(
    list_deposit_data: Sequence[DepositData], deposit_index: int
) -> Tuple[Hash32, ...]:
    tree, root = _make_deposit_tree_and_root(list_deposit_data)
    length_mix_in = len(list_deposit_data).to_bytes(32, byteorder="little")
    merkle_proof = get_merkle_proof(tree, deposit_index)
    merkle_proof_with_mix_in = merkle_proof + (length_mix_in,)
    return merkle_proof_with_mix_in


class Eth1Monitor(Service):
    _w3: web3.Web3
    # FIXME: Change to `LogHandler`
    _log_filter: Any  # FIXME: change to the correct type.
    # TODO: Change to broadcast with lahja: Others can request and get the response.
    _deposit_data: List[DepositData]
    # Sorted
    _block_number_to_hash: Dict[int, Hash32]
    _block_hash_to_accumulated_deposit_count: Dict[Hash32, int]
    _block_timestamp_to_number: "OrderedDict[Timestamp, int]"
    _highest_log_block_number: int

    def __init__(
        self,
        w3: web3.Web3,
        contract_address: bytes,
        contract_abi: str,
        blocks_delayed_to_query_logs: int,
        polling_period: int,
        event_bus: EndpointAPI,
    ) -> None:
        self._w3 = w3
        self._deposit_contract = w3.eth.contract(
            address=contract_address, abi=contract_abi
        )
        self._block_filter = self._w3.eth.filter("latest")
        self._blocks_delayed_to_query_logs = blocks_delayed_to_query_logs
        self._polling_period = polling_period
        self._deposit_data = []
        self._block_number_to_hash = {}
        self._block_hash_to_accumulated_deposit_count = {}
        self._block_timestamp_to_number = OrderedDict()
        self._highest_log_block_number = 0
        self._event_bus = event_bus

    async def run(self) -> None:
        self.manager.run_daemon_task(self._handle_new_logs)
        self.manager.run_daemon_task(self._handle_get_deposit)
        self.manager.run_daemon_task(self._handle_get_eth1_data)
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

    async def _new_logs(self) -> None:
        while True:
            for block_hash in self._get_new_blocks():
                block_number = self._w3.eth.getBlock(block_hash)["number"]
                lookback_block_number = (
                    block_number - self._blocks_delayed_to_query_logs
                )
                if lookback_block_number < 0:
                    continue
                lookback_block = self._w3.eth.getBlock(lookback_block_number)
                self._handle_block_data(
                    lookback_block_number,
                    lookback_block["hash"],
                    lookback_block["parentHash"],
                    lookback_block["timestamp"],
                )
                logs = self._get_logs(lookback_block_number, lookback_block_number)
                for log in logs:
                    yield log, lookback_block["hash"]
            await trio.sleep(self._polling_period)

    def _get_new_blocks(self) -> None:
        # TODO: Replace filter with local states(blockhashs).
        return self._block_filter.get_new_entries()

    def _handle_block_data(
        self,
        block_number: int,
        block_hash: Hash32,
        parent_block_hash: Hash32,
        timestamp: Timestamp,
    ) -> None:
        """
        Put block's data in proper data structures.
        """
        # If we already process a block at `block_number` with different hash,
        # there must have been a fork happening.
        if (block_number in self._block_number_to_hash) and (
            self._block_number_to_hash[block_number] != block_hash
        ):
            raise Eth1Forked(
                f"received block {block_hash}, but at the same height"
                f"we already got block {self._block_number_to_hash[block_number]} before"
            )
        if block_hash in self._block_hash_to_accumulated_deposit_count:
            raise Eth1Forked(
                f"The entry of block {block_hash} has been created before."
                "This indicates there might have been a fork."
            )
        if parent_block_hash not in self._block_hash_to_accumulated_deposit_count:
            self._block_hash_to_accumulated_deposit_count[block_hash] = 0
        else:
            self._block_hash_to_accumulated_deposit_count[
                block_hash
            ] = self._block_hash_to_accumulated_deposit_count[parent_block_hash]
        # Check timestamp
        if len(self._block_timestamp_to_number) != 0:
            latest_timestamp = next(reversed(self._block_timestamp_to_number))
            # TODO: Confirm if the later eth1 blocks should be later than the previous ones.
            #   Raises if its invalid.
            if timestamp < latest_timestamp:
                raise Eth1Forked(
                    "Later blocks with earlier timestamp: "
                    f"latest_timestamp={latest_timestamp}, timestamp={timestamp}"
                )
        self._block_timestamp_to_number[timestamp] = block_number
        self._block_number_to_hash[block_number] = block_hash

    def _process_log(self, log: Dict[Any, Any], block_hash: Hash32) -> None:
        if log["blockHash"] != block_hash:
            raise InvalidEth1Log(
                "`block_hash` of the log does not correspond to the queried block: "
                f"block_hash={block_hash}, log['blockHash']={log['blockHash']}"
            )
        block_number = log["blockNumber"]
        if block_number < self._highest_log_block_number:
            raise InvalidEth1Log(
                f"Received a log from a non-head block. There must have been an re-org. log={log}"
            )
        self._block_hash_to_accumulated_deposit_count[block_hash] += 1
        log_args = log["args"]
        self._deposit_data.append(
            DepositData(
                pubkey=log_args["pubkey"],
                withdrawal_credentials=log_args["withdrawal_credentials"],
                amount=int.from_bytes(log_args["amount"], "little"),
                signature=log_args["signature"],
            )
        )
        if block_number > self._highest_log_block_number:
            self._highest_log_block_number = block_number

    async def _handle_new_logs(self) -> None:
        async for log, block_hash in self._new_logs():
            self._process_log(log, block_hash)

    def _get_deposit(self, deposit_count: int, deposit_index: int) -> Deposit:
        if deposit_index >= deposit_count:
            raise ValueError(
                "`deposit_index` should be smaller than `deposit_count`: "
                f"deposit_index={deposit_index}, deposit_count={deposit_count}"
            )
        len_deposit_data = len(self._deposit_data)
        if deposit_count <= 0 or deposit_count > len_deposit_data:
            raise ValueError(f"invalid `deposit_count`: deposit_count={deposit_count}")
        if deposit_index < 0 or deposit_index >= len_deposit_data:
            raise ValueError(f"invalid `deposit_index`: deposit_index={deposit_index}")
        return Deposit(
            proof=_make_deposit_proof(
                self._deposit_data[:deposit_count], deposit_index
            ),
            data=self._deposit_data[deposit_index],
        )

    def _get_closest_eth1_voting_period_start_block(
        self, target_timestamp: Timestamp
    ) -> Hash32:
        """
        Find the timestamp in `self._block_timestamp_to_number` which is the largest timestamp
        smaller than `target_timestamp`.
        Assume `self._block_timestamp_to_number` is in ascending order, the most naive way to find
        the timestamp is to traverse from the tail of `self._block_timestamp_to_number`.
        """
        # TODO: Change to binary search.
        for timestamp, block_number in reversed(
            self._block_timestamp_to_number.items()
        ):
            if target_timestamp >= timestamp:
                return block_number
        raise Eth1BlockNotFound(
            "Failed to find the closest eth1 voting period start block to "
            f"timestamp {target_timestamp}"
        )

    # https://github.com/ethereum/eth2.0-specs/blob/61f2a0662ebcfb4c097360cc1835c5f01872705c/specs/validator/0_beacon-chain-validator.md#eth1-data  # noqa: E501
    def _get_eth1_data(
        self, distance: int, eth1_voting_period_start_timestamp: Timestamp
    ) -> Eth1Data:
        """
        get_eth1_data(distance: uint64) -> Eth1Data be the (subjective) function that
        returns the Eth 1.0 data at distance relative to
        the Eth 1.0 head at the start of the current Eth 1.0 voting period
        """
        eth1_voting_period_start_block_number = self._get_closest_eth1_voting_period_start_block(
            eth1_voting_period_start_timestamp
        )
        target_block_number = eth1_voting_period_start_block_number - distance
        if target_block_number < 0:
            raise ValueError(
                f"`distance` is larger than `eth1_voting_period_start_block_number`: "
                f"`distance`={distance}, ",
                f"eth1_voting_period_start_block_number={eth1_voting_period_start_block_number}",
            )
        target_block_hash = self._block_number_to_hash[target_block_number]
        # `Eth1Data.deposit_count`: get the `deposit_count` corresponding to the block.
        accumulated_deposit_count = self._block_hash_to_accumulated_deposit_count[
            target_block_hash
        ]
        if accumulated_deposit_count == 0:
            raise ValidationError("failed to make `Eth1Data`: `deposit_count = 0`")
        _, deposit_root = _make_deposit_tree_and_root(
            self._deposit_data[:accumulated_deposit_count]
        )
        return Eth1Data(
            deposit_root=deposit_root,
            deposit_count=accumulated_deposit_count,
            block_hash=target_block_hash,
        )

    async def _handle_get_deposit(self) -> None:
        print("!@# _handle_get_deposit")
        async for req in self._event_bus.stream(GetDepositRequest):
            print(f"!@# _handle_get_deposit: req={req}")
            deposit = self._get_deposit(req.deposit_count, req.deposit_index)
            print(f"!@# _handle_get_deposit: get deposit={deposit}")
            await self._event_bus.broadcast(
                GetDepositResponse(deposit), req.broadcast_config()
            )
            print(f"!@# _handle_get_deposit: finish broadcasting")

    async def _handle_get_eth1_data(self) -> None:
        async for req in self._event_bus.stream(GetEth1DataRequest):
            eth1_data = self._get_eth1_data(
                req.distance, req.eth1_voting_period_start_timestamp
            )
            await self._event_bus.broadcast(
                GetEth1DataResponse(eth1_data), req.broadcast_config()
            )


class BaseEth1MonitorEvent(BaseEvent):
    pass


@dataclass
class GetEth1DataRequest(BaseEth1MonitorEvent):
    distance: int
    eth1_voting_period_start_timestamp: Timestamp


@dataclass
class GetEth1DataResponse(BaseEth1MonitorEvent):
    eth1_data: Eth1Data


@dataclass
class GetDepositRequest(BaseEth1MonitorEvent):
    deposit_count: int
    deposit_index: int


@dataclass
class GetDepositResponse(BaseEth1MonitorEvent):
    deposit: Deposit
