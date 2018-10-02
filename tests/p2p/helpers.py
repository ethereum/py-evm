import random
import string

from cancel_token import CancelToken

from eth_utils import (
    to_bytes,
    keccak,
)

from eth_keys import keys

from p2p import discovery
from p2p import kademlia


def random_address():
    return kademlia.Address(
        '10.0.0.{}'.format(random.randint(0, 255)), random.randint(0, 9999))


def random_node():
    seed = to_bytes(text="".join(random.sample(string.ascii_lowercase, 10)))
    priv_key = keys.PrivateKey(keccak(seed))
    return kademlia.Node(priv_key.public_key, random_address())


def get_discovery_protocol(seed=b"seed", address=None):
    privkey = keys.PrivateKey(keccak(seed))
    if address is None:
        address = random_address()
    return discovery.DiscoveryProtocol(privkey, address, [], CancelToken("discovery-test"))
