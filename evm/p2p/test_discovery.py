from eth_utils import decode_hex

from evm.p2p import discovery
from evm.p2p import kademlia


def test_get_max_neighbours_per_packet():
    proto = get_discovery_protocol()
    # This test is just a safeguard against changes that inadvertently modify the behaviour of
    # _get_max_neighbours_per_packet().
    assert proto._get_max_neighbours_per_packet() == 12


def get_discovery_protocol():
    privkey = decode_hex('65462b0520ef7d3df61b9992ed3bea0c56ead753be7c8b3614e0ce01e4cac41b')
    addr = kademlia.Address('127.0.0.1', 30303)
    return discovery.DiscoveryProtocol(privkey, addr, bootstrap_nodes=[])
