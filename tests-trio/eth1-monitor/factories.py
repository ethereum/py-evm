from trinity.components.eth2.eth1_monitor.eth1_monitor import Eth1Monitor

from p2p.trio_service import background_service

from async_generator import asynccontextmanager
from lahja.trio.endpoint import TrioEndpoint


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
