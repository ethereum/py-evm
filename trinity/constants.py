from pathlib import Path
from typing import Dict, Tuple

from lahja import (
    BroadcastConfig,
)

from eth_utils import (
    decode_hex,
)

from eth_keys import (
    keys,
)

from p2p.kademlia import Address, Node


# application identifier
APP_IDENTIFIER_ETH1 = "eth1"
APP_IDENTIFIER_BEACON = "beacon"

# The file path to the non-python assets
ASSETS_DIR = Path(__file__).parent / "assets"
IPC_DIR = 'ipcs'
LOG_DIR = 'logs'
LOG_FILE = 'trinity.log'
PID_DIR = 'pids'

# sync modes
SYNC_FULL = 'full'
SYNC_FAST = 'fast'
SYNC_LIGHT = 'light'
SYNC_BEAM = 'beam'

# lahja endpoint names
MAIN_EVENTBUS_ENDPOINT = 'main'
NETWORKDB_EVENTBUS_ENDPOINT = 'network-db'
NETWORKING_EVENTBUS_ENDPOINT = 'networking'
TO_NETWORKING_BROADCAST_CONFIG = BroadcastConfig(filter_endpoint=NETWORKING_EVENTBUS_ENDPOINT)

# Network IDs: https://ethereum.stackexchange.com/questions/17051/how-to-select-a-network-id-or-is-there-a-list-of-network-ids/17101#17101  # noqa: E501
MAINNET_NETWORK_ID = 1
ROPSTEN_NETWORK_ID = 3


# Default preferred enodes
DEFAULT_PREFERRED_NODES: Dict[int, Tuple[Node, ...]] = {
    MAINNET_NETWORK_ID: (
        Node(keys.PublicKey(decode_hex("1118980bf48b0a3640bdba04e0fe78b1add18e1cd99bf22d53daac1fd9972ad650df52176e7c7d89d1114cfef2bc23a2959aa54998a46afcf7d91809f0855082")),  # noqa: E501
             Address("52.74.57.123", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("78de8a0916848093c73790ead81d1928bec737d565119932b98c6b100d944b7a95e94f847f689fc723399d2e31129d182f7ef3863f2b4c820abbf3ab2722344d")),  # noqa: E501
             Address("191.235.84.50", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("ddd81193df80128880232fc1deb45f72746019839589eeb642d3d44efbb8b2dda2c1a46a348349964a6066f8afb016eb2a8c0f3c66f32fadf4370a236a4b5286")),  # noqa: E501
             Address("52.231.202.145", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("3f1d12044546b76342d59d4a05532c14b85aa669704bfe1f864fe079415aa2c02d743e03218e57a33fb94523adb54032871a6c51b2cc5514cb7c7e35b3ed0a99")),  # noqa: E501
             Address("13.93.211.84", 30303, 30303)),
    ),
    ROPSTEN_NETWORK_ID: (
        Node(keys.PublicKey(decode_hex("053d2f57829e5785d10697fa6c5333e4d98cc564dbadd87805fd4fedeb09cbcb642306e3a73bd4191b27f821fb442fcf964317d6a520b29651e7dd09d1beb0ec")),  # noqa: E501
             Address("79.98.29.154", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("94c15d1b9e2fe7ce56e458b9a3b672ef11894ddedd0c6f247e0f1d3487f52b66208fb4aeb8179fce6e3a749ea93ed147c37976d67af557508d199d9594c35f09")),  # noqa: E501
             Address("192.81.208.223", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("a147a3adde1daddc0d86f44f1a76404914e44cee018c26d49248142d4dc8a9fb0e7dd14b5153df7e60f23b037922ae1f33b8f318844ef8d2b0453b9ab614d70d")),  # noqa: E501
             Address("72.36.89.11", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("d8714127db3c10560a2463c557bbe509c99969078159c69f9ce4f71c2cd1837bcd33db3b9c3c3e88c971b4604bbffa390a0a7f53fc37f122e2e6e0022c059dfd")),  # noqa: E501
             Address("51.15.217.106", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("efc75f109d91cdebc62f33be992ca86fce2637044d49a954a8bdceb439b1239afda32e642456e9dfd759af5b440ef4d8761b9bda887e2200001c5f3ab2614043")),  # noqa: E501
             Address("34.228.166.142", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("c8b9ec645cd7fe570bc73740579064c528771338c31610f44d160d2ae63fd00699caa163f84359ab268d4a0aed8ead66d7295be5e9c08b0ec85b0198273bae1f")),  # noqa: E501
             Address("178.62.246.6", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("7a34c02d5ef9de43475580cbb88fb492afb2858cfc45f58cf5c7088ceeded5f58e65be769b79c31c5ae1f012c99b3e9f2ea9ef11764d553544171237a691493b")),  # noqa: E501
             Address("35.227.38.243", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("bbb3ad8be9684fa1d67ac057d18f7357dd236dc01a806fef6977ac9a259b352c00169d092c50475b80aed9e28eff12d2038e97971e0be3b934b366e86b59a723")),  # noqa: E501
             Address("81.169.153.213", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("30b7ab30a01c124a6cceca36863ece12c4f5fa68e3ba9b0b51407ccc002eeed3b3102d20a88f1c1d3c3154e2449317b8ef95090e77b312d5cc39354f86d5d606")),  # noqa: E501
             Address("52.176.7.10", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("02508da84b37a1b7f19f77268e5b69acc9e9ab6989f8e5f2f8440e025e633e4277019b91884e46821414724e790994a502892144fc1333487ceb5a6ce7866a46")),  # noqa: E501
             Address("54.175.255.230", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("0eec3472a46f0b637045e41f923ce1d4a585cd83c1c7418b183c46443a0df7405d020f0a61891b2deef9de35284a0ad7d609db6d30d487dbfef72f7728d09ca9")),  # noqa: E501
             Address("181.168.193.197", 30303, 30303)),
        Node(keys.PublicKey(decode_hex("643c31104d497e3d4cd2460ff0dbb1fb9a6140c8bb0fca66159bbf177d41aefd477091c866494efd3f1f59a0652c93ab2f7bb09034ed5ab9f2c5c6841aef8d94")),  # noqa: E501
             Address("34.198.237.7", 30303, 30303)),
    ),
}

# Amount of time a peer will be blacklisted if their network or genesis hash does not match
BLACKLIST_SECONDS_WRONG_NETWORK_OR_GENESIS = 600
