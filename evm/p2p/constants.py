CLIENT_VERSION_STRING = "Py-EVM"

SUPPORTED_RLPX_VERSION = 4

# Overhead added by ECIES encryption
ENCRYPT_OVERHEAD_LENGTH = 113

# Lentgh of elliptic S256 signatures
SIGNATURE_LEN = 65

# Length of public keys: 512 bit keys in uncompressed form, without format byte
PUBKEY_LEN = 64

# Hash length (for nonce etc)
HASH_LEN = 32

# Length of initial auth handshake message
AUTH_MSG_LEN = SIGNATURE_LEN + HASH_LEN + PUBKEY_LEN + HASH_LEN + 1

# Length of auth ack handshake message
AUTH_ACK_LEN = PUBKEY_LEN + HASH_LEN + 1

# Length of encrypted pre-EIP-8 initiator handshake
ENCRYPTED_AUTH_MSG_LEN = AUTH_MSG_LEN + ENCRYPT_OVERHEAD_LENGTH

# Length of encrypted pre-EIP-8 handshake reply
ENCRYPTED_AUTH_ACK_LEN = AUTH_ACK_LEN + ENCRYPT_OVERHEAD_LENGTH

# Length of an RLPx packet's header
HEADER_LEN = 16

# Length of an RLPx header's/frame's MAC
MAC_LEN = 16

# The amount of seconds a connection can be idle.
CONN_IDLE_TIMEOUT = 30

# Total time, in seconds, for a complete encryption/P2P handshake, both ways.
HANDSHAKE_TIMEOUT = 5

# Timeout used when waiting for a reply from a remote node.
REPLY_TIMEOUT = 3

# Max number of items we can ask for in LES requests. These are the values used in geth and if we
# ask for more than this the peers will disconnect from us.
MAX_HEADERS_FETCH = 192
MAX_BODIES_FETCH = 32
MAX_RECEIPTS_FETCH = 128
MAX_CODE_FETCH = 64
MAX_PROOFS_FETCH = 64
MAX_HEADER_PROOFS_FETCH = 64
