from trinity.plugins.eth2.beacon.eth1_monitor import Eth1Monitor

from p2p.trio_service import background_service

from async_generator import asynccontextmanager


@asynccontextmanager
async def Eth1MonitorFactory(
    w3, registration_contract, blocks_delayed_to_query_logs, polling_period
):
    m = Eth1Monitor(
        w3,
        registration_contract.address,
        registration_contract.abi,
        blocks_delayed_to_query_logs,
        polling_period,
    )
    async with background_service(m):
        yield m
