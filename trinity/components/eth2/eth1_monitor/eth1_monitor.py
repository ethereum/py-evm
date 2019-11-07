from collections import OrderedDict
from typing import Any, AsyncGenerator, List, Dict, NamedTuple, Sequence, Tuple

from eth_typing import Hash32
from eth_utils import ValidationError

from lahja import EndpointAPI
import trio
from web3 import Web3
from web3.utils.events import get_event_data

from eth_utils import encode_hex, event_abi_to_log_topic

from eth2.beacon.typing import Timestamp
from eth2.beacon.typing import Gwei
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.eth1_data import Eth1Data
from eth2._utils.merkle.sparse import calc_merkle_tree_from_leaves, get_root
from eth2._utils.merkle.common import MerkleTree, get_merkle_proof
from eth2._utils.hash import hash_eth2

from p2p.trio_service import Service


from .exceptions import InvalidEth1Log, Eth1Forked, Eth1BlockNotFound
from .events import (
    GetDepositResponse,
    GetDepositRequest,
    GetEth1DataRequest,
    GetEth1DataResponse,
)


# TODO: Is there a better typing for `Log`?
Log = Dict[Any, Any]


class Eth1Block(NamedTuple):
    block_hash: Hash32
    parent_hash: Hash32
    number: int
    timestamp: int


class DepositLog(NamedTuple):
    pass


def _w3_get_latest_block(w3: Web3, *args: Any, **kwargs: Any) -> Eth1Block:
    block_dict = w3.eth.getBlock(*args, **kwargs)
    return Eth1Block(
        block_hash=block_dict["hash"],
        number=int(block_dict["number"]),
        parent_hash=block_dict["parentHash"],
        timestamp=int(block_dict["timestamp"]),
    )


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
    length_mix_in = Hash32(len(list_deposit_data).to_bytes(32, byteorder="little"))
    merkle_proof = get_merkle_proof(tree, deposit_index)
    merkle_proof_with_mix_in = merkle_proof + (length_mix_in,)
    return merkle_proof_with_mix_in


class Eth1Monitor(Service):
    _w3: Web3

    _deposit_data: List[DepositData]
    # Sorted
    _block_number_to_hash: Dict[int, Hash32]
    _block_hash_to_accumulated_deposit_count: Dict[Hash32, int]
    _block_timestamp_to_number: "OrderedDict[Timestamp, int]"

    def __init__(
        self,
        w3: Web3,
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
        self._blocks_delayed_to_query_logs = blocks_delayed_to_query_logs
        self._polling_period = polling_period
        self._deposit_data = []
        self._block_number_to_hash = {}
        self._block_hash_to_accumulated_deposit_count = {}
        self._block_timestamp_to_number = OrderedDict()
        self._event_bus = event_bus

    async def run(self) -> None:
        self.manager.run_daemon_task(self._handle_new_logs)
        self.manager.run_daemon_task(self._handle_get_deposit)
        self.manager.run_daemon_task(self._handle_get_eth1_data)
        await self.manager.wait_stopped()

    def _get_logs(self, from_block: int, to_block: int) -> Sequence[Log]:
        # NOTE: Another way, create and uninstall a filter.
        # log_filter = self._deposit_contract.events.DepositEvent.createFilter(
        #     fromBlock=from_block, toBlock=to_block
        # )
        # logs = log_filter.get_new_entries()
        # self._w3.eth.uninstallFilter(log_filter.filter_id)

        # NOTE: web3 v4 does not support `events.Event.getLogs`.
        # We should change the install-and-uninstall pattern to it after we update to v5.
        event = self._deposit_contract.events.DepositEvent
        event_abi = event._get_event_abi()
        logs = self._w3.eth.getLogs(
            {
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": self._deposit_contract.address,
                "topics": [encode_hex(event_abi_to_log_topic(event_abi))],
            }
        )
        parsed_logs = tuple(get_event_data(event_abi, log) for log in logs)
        return parsed_logs

    async def _new_blocks(self) -> AsyncGenerator[Eth1Block, None]:
        highest_processed_delayed_block_number = 0
        while True:
            block = _w3_get_latest_block(self._w3, "latest")
            target_delayed_block_number = (
                block.number - self._blocks_delayed_to_query_logs
            )
            if target_delayed_block_number > highest_processed_delayed_block_number:
                # From `highest_processed_delayed_block_number` to `target_delayed_block_number`
                for block_number in range(
                    highest_processed_delayed_block_number + 1,
                    target_delayed_block_number + 1,
                ):
                    block = _w3_get_latest_block(self._w3, block_number)
                    self._handle_block_data(block)
                    yield block
                highest_processed_delayed_block_number = target_delayed_block_number
            await trio.sleep(self._polling_period)

    def _handle_block_data(self, block: Eth1Block) -> None:
        """
        Put block's data in proper data structures.
        """
        # If we already process a block at `block_number` with different hash,
        # there must have been a fork happening.
        if (block.number in self._block_number_to_hash) and (
            self._block_number_to_hash[block.number] != block.block_hash
        ):
            raise Eth1Forked(
                f"received block {block.block_hash}, but at the same height"
                f"we already got block {self._block_number_to_hash[block.number]} before"
            )
        if block.block_hash in self._block_hash_to_accumulated_deposit_count:
            raise Eth1Forked(
                f"The entry of block {block.block_hash} has been created before."
                "This indicates there might have been a fork."
            )
        if block.parent_hash not in self._block_hash_to_accumulated_deposit_count:
            self._block_hash_to_accumulated_deposit_count[block.block_hash] = 0
        else:
            self._block_hash_to_accumulated_deposit_count[
                block.block_hash
            ] = self._block_hash_to_accumulated_deposit_count[block.parent_hash]
        # Check timestamp
        if len(self._block_timestamp_to_number) != 0:
            latest_timestamp = next(reversed(self._block_timestamp_to_number))
            if block.timestamp < latest_timestamp:
                raise Eth1Forked(
                    "Later blocks with earlier timestamp: "
                    f"latest_timestamp={latest_timestamp}, timestamp={block.timestamp}"
                )
        self._block_timestamp_to_number[block.timestamp] = block.number
        self._block_number_to_hash[block.number] = block.block_hash

    def _process_log(self, log: Log) -> None:
        self._block_hash_to_accumulated_deposit_count[log["blockHash"]] += 1
        log_args = log["args"]
        self._deposit_data.append(
            DepositData(
                pubkey=log_args["pubkey"],
                withdrawal_credentials=log_args["withdrawal_credentials"],
                amount=Gwei(int.from_bytes(log_args["amount"], "little")),
                signature=log_args["signature"],
            )
        )

    async def _handle_new_logs(self) -> None:
        async for block in self._new_blocks():
            logs = self._get_logs(block.number, block.number)
            for log in logs:
                self._process_log(log)

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
    ) -> int:
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
        async for req in self._event_bus.stream(GetDepositRequest):
            deposit = self._get_deposit(req.deposit_count, req.deposit_index)
            await self._event_bus.broadcast(
                GetDepositResponse.from_data(deposit), req.broadcast_config()
            )

    async def _handle_get_eth1_data(self) -> None:
        async for req in self._event_bus.stream(GetEth1DataRequest):
            eth1_data = self._get_eth1_data(
                req.distance, req.eth1_voting_period_start_timestamp
            )
            await self._event_bus.broadcast(
                GetEth1DataResponse.from_data(eth1_data), req.broadcast_config()
            )
