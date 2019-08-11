from typing import (
    NamedTuple,
    Set,
)

# Reference: https://github.com/ethereum/eth2.0-specs/blob/dev/specs/networking/p2p-interface.md

#
# Network Fundamentals
#

# FIXME: Change to
#   Insecure: when /plaintext/2.0.0 is finalized and implemented in py-libp2p
#   or
#   Secure
SECURITY_PROTOCOL_ID = "/insecure/1.0.0"

MULTISELECT_PROTOCOL_ID = "/multistream/1.0.0"

MULTIPLEXING_PROTOCOL_ID = "/mplex/6.7.0"


#
# Network configuration
#

# TODO: TBD
# The max size of uncompressed req/resp messages that clients will allow.
REQ_RESP_MAX_SIZE = 2 ** 32 - 1  # 4 GiB
# The max size of uncompressed gossip messages.
GOSSIP_MAX_SIZE = 2 ** 20  # 1 MiB
# TODO: TBD
# The number of shard subnets used in the gossipsub protocol.
SHARD_SUBNET_COUNT = None
# Maximum time to wait for first byte of request response (time-to-first-byte).
TTFB_TIMEOUT = 5  # seconds
# Maximum time for complete response transfer.
RESP_TIMEOUT = 10  # seconds


#
# Gossip domain
#

GOSSIPSUB_PROTOCOL_ID = "/meshsub/1.0.0"


# Parameters
class GossipsubParams(NamedTuple):
    # `D` (topic stable mesh target count)
    DEGREE: int = 6
    # `D_low` (topic stable mesh low watermark)
    DEGREE_LOW: int = 4
    # `D_high` (topic stable mesh high watermark)
    DEGREE_HIGH: int = 12
    # `D_lazy` (gossip target)
    # NOTE: This is the same number as `D` in go-libp2p-pubsub.
    #   Ref: https://github.com/libp2p/go-libp2p-pubsub/blob/5e883d794c9ff281d6ef42d2309dc26532d2d34b/gossipsub.go#L513  # noqa: E501
    DEGREE_LAZY: int = 6
    # `fanout_ttl` (ttl for fanout maps for topics we are not subscribed to
    #   but have published to seconds).
    FANOUT_TTL: int = 60
    # `gossip_advertise` (number of windows to gossip about).
    GOSSIP_WINDOW: int = 3
    # `gossip_history` (number of heartbeat intervals to retain message IDs).
    GOSSIP_HISTORY: int = 5
    # `heartbeat_interval` (frequency of heartbeat, seconds).
    HEARTBEAT_INTERVAL: int = 1  # seconds


# Topics
PUBSUB_TOPIC_BEACON_BLOCK = "beacon_block"
PUBSUB_TOPIC_BEACON_ATTESTATION = "beacon_attestation"
PUBSUB_TOPIC_SHARD_ATTESTATION_FMT = "shard{}_attestation"
PUBSUB_TOPIC_VOLUNTARY_EXIT = "voluntary_exit"
PUBSUB_TOPIC_PROPOSER_SLASHING = "proposer_slashing"
PUBSUB_TOPIC_ATTESTER_SLASHING = "attester_slashing"

PUBSUB_TOPIC_ENCODE_POSTFIX = "ssz"
PUBSUB_TOPIC_ENCODE_COMPRESS_POSTFIX = "ssz_snappy"


#
# Req/Resp domain
#

REQ_RESP_PROTOCOL_PREFIX = "/eth2/beacon_chain/req"


class ResponseCode:
    class StandardCodes(NamedTuple):
        SUCCESS: int = 0
        INVALID_REQUEST: int = 1
        SERVER_ERROR: int = 2
    # Make mypy happy, but duplicated with the code above.
    SUCCESS: "ResponseCode"
    INVALID_REQUEST: "ResponseCode"
    SERVER_ERROR: "ResponseCode"

    _standard_codes = StandardCodes()
    _standard_codes_value_to_name = {
        value: key for key, value in _standard_codes._asdict().items()
    }
    _non_standard_codes = tuple(range(128, 256))

    _code: int

    def __init__(self, code: int) -> None:
        self._validate(code)
        self._code = code

    def __repr__(self) -> str:
        if self._code in self._standard_codes:
            name = self._standard_codes_value_to_name[self._code]
            return f"<ResponseCode {name}>"
        else:
            return f"<ResponseCode #{self._code}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ResponseCode):
            return NotImplemented
        return self._code == other._code

    @property
    def valid_codes(self) -> Set[int]:
        return set(self._standard_codes).union(self._non_standard_codes)

    def _validate(self, code: int) -> None:
        if code < 0 or code >= 256:
            raise ValueError("`code` should be in the range [0, 256)")
        if code not in self.valid_codes:
            raise ValueError(f"`code` should be in valid_codes={self.valid_codes}")

    def to_int(self) -> int:
        return self._code

    def to_bytes(self) -> bytes:
        return self._code.to_bytes(1, "big")

    @classmethod
    def from_bytes(cls, code_bytes: bytes) -> "ResponseCode":
        if len(code_bytes) != 1:
            raise ValueError("length of the bytes repr of code should be exactly 1")
        return cls(code_bytes[0])


# Set the standard codes as the class attributes.
# e.g. ResponseCode.SUCCESS
for code_name, code_value in ResponseCode._standard_codes._asdict().items():
    setattr(ResponseCode, code_name, ResponseCode(code_value))


REQ_RESP_VERSION = "1"
REQ_RESP_ENCODE_POSTFIX = "ssz"
REQ_RESP_ENCODE_COMPRESS_POSTFIX = "ssz_snappy"
REQ_RESP_HELLO = "hello"
REQ_RESP_GOODBYE = "goodbye"
REQ_RESP_BEACON_BLOCKS = "beacon_blocks"
REQ_RESP_RECENT_BEACON_BLOCKS = "recent_beacon_blocks"
