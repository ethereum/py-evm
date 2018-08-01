# Max number of items we can ask for in LES requests. These are the values used in geth and if we
# ask for more than this the peers will disconnect from us.
MAX_HEADERS_FETCH = 192
MAX_BODIES_FETCH = 32
MAX_RECEIPTS_FETCH = 128
MAX_CODE_FETCH = 64
MAX_PROOFS_FETCH = 64
MAX_HEADER_PROOFS_FETCH = 64

# Types of LES Announce messages
LES_ANNOUNCE_SIMPLE = 1
LES_ANNOUNCE_SIGNED = 2
