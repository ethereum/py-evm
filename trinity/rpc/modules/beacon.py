from trinity.rpc.modules import RPCModule


class Beacon(RPCModule):

    @property
    def name(self) -> str:
        return 'beacon'

    async def currentSlot(self) -> str:
        return hex(666)
