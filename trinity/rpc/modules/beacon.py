from trinity.rpc.modules import BeaconChainRPCModule


class Beacon(BeaconChainRPCModule):

    @property
    def name(self) -> str:
        return 'beacon'

    async def currentSlot(self) -> str:
        return hex(666)
