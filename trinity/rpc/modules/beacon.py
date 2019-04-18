from trinity.rpc.modules import BeaconChainRPCModule


class Beacon(BeaconChainRPCModule):

    async def currentSlot(self) -> str:
        return hex(666)
