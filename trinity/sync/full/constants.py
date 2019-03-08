# How old (in seconds) must our local head be to cause us to start with a
# fast-sync before we switch to regular-sync.
FAST_SYNC_CUTOFF = 60 * 60 * 24

# How many headers/blocks should we queue up waiting to be persisted?
# This buffer size is estimated using: NUM_BLOCKS_PERSISTED_PER_SEC * BUFFER_SECONDS * MARGIN
#
# NUM_BLOCKS_PERSISTED_PER_SEC = 200
#   (rough estimate from personal NVMe SSD, with small blocks on Ropsten)
#
# BUFFER_SECONDS = 30
#   (this should allow plenty of time for peers to fill in the buffer during db writes)
#
HEADER_QUEUE_SIZE_TARGET = 6000

# How many blocks to persist at a time
# Only need a few seconds of buffer on the DB write side.
BLOCK_QUEUE_SIZE_TARGET = 1000
