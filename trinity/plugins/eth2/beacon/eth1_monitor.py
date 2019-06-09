from typing import Any

import trio

import web3

from p2p.trio_service import Service


# https://github.com/ethereum/eth2.0-specs/blob/dev/deposit_contract/contracts/validator_registration.v.py#L10-L16  # noqa: E501


PERIOD_VOTING_BLOCK = 1000


class Eth1Monitor(Service):
    _w3: web3.Web3
    _log_filter: Any  # FIXME: change to the correct type.
    # TODO: Change to broadcast with lahja: Others can request and get the response.

    def __init__(
        self,
        w3: web3.Web3,
        contract_address: bytes,
        contract_abi: str,
        since_block_height: int,
        logs_lookback_period: int,
    ) -> None:
        self._w3 = w3
        self._deposit_contract = w3.eth.contract(
            address=contract_address, abi=contract_abi
        )
        self._log_filter = self._deposit_contract.events.DepositEvent.createFilter(
            fromBlock=since_block_height
        )
        self.logs_lookback_period = logs_lookback_period

    async def run(self) -> None:
        send_channel, receive_channel = trio.open_memory_channel(0)
        self.manager.run_daemon_task(self._poll_new_logs, send_channel)
        self.manager.run_daemon_task(self._count_eth1_data, receive_channel)
        await self.manager.wait_stopped()

    async def _poll_new_logs(self, send_channel) -> None:
        async with send_channel:
            while True:
                for log in self._log_filter.get_new_entries():
                    await send_channel.send(log)
                await trio.sleep(0.1)

    # TODO: (?)
    async def _count_eth1_data(self, receive_channel) -> None:
        async with receive_channel:
            async for value in receive_channel:
                print("!@# receive value", value)

    # TODO: Generate `block_hash`
    # TODO: Add filter to new blocks. For each new block, we
    #   Every around 1000(?) blocks, we decide a `block_hash` which
    #   should be voted by the validators.
