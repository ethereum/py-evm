import pytest


@pytest.fixture(autouse=True)
def _network_sim(router):
    network = router.get_network(name='simulated')
    with network.patch_asyncio():
        yield network
