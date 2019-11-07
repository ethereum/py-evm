from typing import Any, AsyncGenerator, Dict, List, NamedTuple, Tuple
from abc import ABC, abstractmethod

import trio


from eth_utils import to_dict
from eth_typing import Hash32
from web3 import Web3

from p2p.trio_service import Service


class Eth1Block(NamedTuple):
    block_hash: Hash32
    parent_hash: Hash32
    number: int
    timestamp: int


def _w3_get_latest_block(w3: Web3, *args: Any, **kwargs: Any) -> Eth1Block:
    block_dict = w3.eth.getBlock(*args, **kwargs)
    return Eth1Block(
        block_hash=block_dict["hash"],
        number=int(block_dict["number"]),
        parent_hash=block_dict["parentHash"],
        timesttamp=int(block_dict["timestamp"]),
    )


class BaseBlockFilter(ABC):
    @abstractmethod
    async def get_blocks_after_period(
        self, number_blocks_period: int
    ) -> AsyncGenerator[Eth1Block, None]:
        pass


def _get_recent_blocks(w3: Web3, history_size: int) -> Tuple[Eth1Block, ...]:
    """
    Get the recent `history_size` blocks, or back until the genesis block, from web3.
    """
    block = _w3_get_latest_block(w3, "latest")
    recent_blocks = [block]
    # initialize the list of recent hashes
    for _ in range(history_size - 1):
        # break the loop if we hit the genesis block.
        if block.number == 0:
            break
        block = _w3_get_latest_block(w3, block.parent_hash)
        recent_blocks.append(block)
    reversed_recent_blocks = tuple(reversed(recent_blocks))
    return reversed_recent_blocks


def _check_chain_head(
    w3: Web3, recent_blocks: Tuple[Eth1Block, ...], history_size: int
) -> Tuple[Tuple[Eth1Block, ...], Tuple[Eth1Block, ...]]:
    # TODO: Need optimizations. Now there are too many linear searches.
    block = _w3_get_latest_block(w3, "latest")
    new_blocks = []
    # Get up to `history_size` new blocks from `web3`. "New blocks" mean the blocks that
    # are not present in `recent_blocks`.
    for _ in range(history_size):
        # TODO: Optimization
        if block in recent_blocks:
            break
        new_blocks.append(block)
        block = _w3_get_latest_block(w3, block.parent_hash)
    else:
        raise Exception(f"No common ancestor found for block: {block.block_hash}")

    # Here, `block` must be the common ancestor of the new chain and the previous chain.

    # TODO: Optimization
    first_common_ancestor_idx = recent_blocks.index(block)

    revoked_blocks = recent_blocks[(first_common_ancestor_idx + 1) :]

    # Reverse it to make its order from oldest to the latest.
    reversed_new_blocks = tuple(reversed(new_blocks))

    return revoked_blocks, reversed_new_blocks


class BlockFilter(Service, BaseBlockFilter):
    _w3: Web3
    _history_size: int
    _recent_blocks: Tuple[Hash32, ...]
    _time_polling_period: float
    _new_delayed_block_channel: trio.abc.ReceiveChannel[Eth1Block]
    _highest_delayed_block_number: int
    _num_blocks_delayed: int

    def __init__(
        self,
        w3: Web3,
        history_size: int,
        time_polling_period: float,
        num_blocks_delayed: int,
    ) -> None:
        self._w3 = w3
        if num_blocks_delayed >= history_size:
            raise ValueError(
                f"num_blocks_delayed={num_blocks_delayed} should be smaller than"
                f"history_size={history_size}"
            )
        self._history_size = history_size
        # ----------> higher score
        self._recent_blocks = _get_recent_blocks(self._w3, self._history_size)
        self._time_polling_period = time_polling_period
        self._num_blocks_delayed = num_blocks_delayed
        self._highest_delayed_block_number = -1

    async def run(self) -> None:
        send_channel, receive_channel = trio.open_memory_channel()
        self._new_delayed_block_channel = receive_channel
        self.manager.run_daemon_task(self._handle_new_blocks, send_channel)
        await self.manager.wait_stopped()

    def _poll_new_blocks(self) -> Tuple[Eth1Block, ...]:
        revoked_blocks, new_blocks = _check_chain_head(
            self._w3, self._recent_blocks, self._history_size
        )
        # Determine `unchanged_blocks` by `revoked_blocks`.
        # NOTE: Use if/else to avoid self._recent_blocks[:-1 * 0]
        #       when len(revoked_blocks) == 0
        unchanged_block_hashes: Tuple[Hash32]
        if len(revoked_blocks) != 0:
            unchanged_block_hashes = self._recent_block_hashes[
                : -1 * len(revoked_blocks)
            ]
        else:
            unchanged_block_hashes = self._recent_block_hashes
        # Append new blocks to `unchanged_blocks`, and move revoked ones out of
        # `self._recent_blocks`
        new_recent_blocks = unchanged_block_hashes + new_blocks

        # Handle new delayed blocks
        new_delayed_blocks = []
        for block in new_blocks:
            if self._highest_delayed_block_number < block.number:
                new_delayed_blocks.append(block)
                self._highest_delayed_block_number = block.number

        # Keep `len(self._recent_blocks) <= self._history_size`
        self._recent_blocks = new_recent_blocks[(-1 * self._history_size) :]

        return tuple(new_delayed_blocks)

    async def _handle_new_blocks(
        self, send_channel: trio.abc.SendChannel[Eth1Block]
    ) -> None:
        while True:
            for block in self._poll_new_blocks():
                await send_channel.send(block)
            await trio.sleep(self._time_polling_period)

    async def get_delayed_new_blocks(self) -> AsyncGenerator[Eth1Block, None]:
        pass
