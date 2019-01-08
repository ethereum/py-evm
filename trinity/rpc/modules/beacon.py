from trinity.rpc.modules import BeaconRPCModule


class Beacon(BeaconRPCModule):

    @property
    def name(self) -> str:
        return 'beacon'

    async def currentSlot(self) -> str:
        return hex(666)
