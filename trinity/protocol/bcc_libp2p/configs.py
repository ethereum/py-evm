from typing import (
    NamedTuple,
)

#
# Libp2p standard protocols
#   - Refer to https://github.com/ethereum/eth2.0-specs/blob/dev/specs/networking/libp2p-standardization.md  # noqa: E501
#

# FIXME: Change to
#   Insecure: when /plaintext/2.0.0 is finalized and implemented in py-libp2p
#   or
#   Secure
SECURITY_PROTOCOL_ID = "/insecure/1.0.0"

MULTISELECT_PROTOCOL_ID = "/multistream/1.0.0"

MULTIPLEXING_PROTOCOL_ID = "/mplex/6.7.0"

PUBSUB_PROTOCOL_ID = "/eth/serenity/gossipsub/1.0.0"

PUBSUB_TOPIC_BEACON_BLOCK = "beacon_block"
PUBSUB_TOPIC_BEACON_ATTESTATION = "beacon_attestation"
PUBSUB_TOPIC_SHARD_ATTESTATION_FMT = "shard{}_attestation"

PUBSUB_MSG_SIZE = 512 * (2 ** 10)  # 512KB

RPC_PROTOCOL_PREFIX = "/eth/serenity/rpc"


#
# Node Identification
#   - Refer to https://github.com/ethereum/eth2.0-specs/blob/dev/specs/networking/node-identification.md  # noqa: E501
#
DEFAULT_PORT = 9000

# PeerID: SHA2-256 multihash
# Key algo: secp256k1


class GossipsubParams(NamedTuple):
    DEGREE: int = 6
    DEGREE_LOW: int = 4
    DEGREE_HIGH: int = 12
    FANOUT_TTL: int = 60
    GOSSIP_WINDOW: int = 3
    GOSSIP_HISTORY: int = 5
    HEARTBEAT_INTERVAL: int = 1
