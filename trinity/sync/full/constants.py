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

# How many blocks to import at a time
# Only need a few seconds of buffer on the DB side
# This is specifically for blocks where execution happens locally.
# So each block might have a pretty significant execution time, on
#   the order of seconds.
# This is also used during Beam sync (maybe we should have a different constant?)
# The number is derived by:
#   - number of parallel processes running (currently 4)
#   - how many block executions can run comfortably in a single process (~2)
#       About half the time is spent executing, and the other half waiting on nodes
#       This might change when we start benchmarking against remote nodes
#   - how many blocks finish early/quickly, ~half, which doubles capacity (~2)
#   So we multiply all these together to get 16 parallel executions to permit.
#   The first block in the queue doesn't get previewed, which brings us to 17.
BLOCK_IMPORT_QUEUE_SIZE = 17
