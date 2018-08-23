import asyncio

from lahja import (
    Endpoint
)

from trinity.events import (
    PeerCountRequest,
    PeerCountResponse,
)

def run_test_proc(event_bus: Endpoint):
    print("hello from test proc")
    loop = asyncio.get_event_loop()
    event_bus.connect()

    asyncio.ensure_future(request_receive_peer_count(event_bus))
    loop.run_forever()
    loop.close()


async def request_receive_peer_count(event_bus):
    while True:
        response = await event_bus.request(PeerCountRequest())
        print("Peer Count: " + str(response.payload))
        await asyncio.sleep(1)

