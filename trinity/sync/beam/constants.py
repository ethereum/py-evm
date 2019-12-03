from eth.constants import MAX_UNCLE_DEPTH

# Peers are typically expected to have predicted nodes available,
#   so it's reasonable to ask for all-predictive nodes from a peer.
# Urgent node requests usually come in pretty fast, so
#   even at a small value (like 1ms), this timeout is rarely triggered.
DELAY_BEFORE_NON_URGENT_REQUEST = 0.05

# How much large should our buffer be? This is a multiplier on how many
# nodes we can request at once from a single peer.
REQUEST_BUFFER_MULTIPLIER = 16

# How many different processes are running previews? They will split the
# block imports equally. A higher number means a slower startup, but more
# previews are possible at a time (given that you have enough CPU cores).
# The sensitivity of this number is relatively unexplored.
NUM_PREVIEW_SHARDS = 4

# How many speculative executions should we run concurrently? This is
#   a global number, not per process or thread. It is necessary to
#   constrain the I/O, which can become the global bottleneck.
MAX_CONCURRENT_SPECULATIVE_EXECUTIONS = 40
MAX_SPECULATIVE_EXECUTIONS_PER_PROCESS = MAX_CONCURRENT_SPECULATIVE_EXECUTIONS // NUM_PREVIEW_SHARDS

# If a peer does something not ideal, give it a little time to breath,
# and maybe to try out another peeer. Then reinsert it relatively soon.
# Measured in seconds.
NON_IDEAL_RESPONSE_PENALTY = 0.5

# How many seconds should we leave the backfill peer idle, in between
# backfill requests? This is called "tests" because we are importantly
# checking how fast a peer is.
GAP_BETWEEN_TESTS = 0.25
# One reason to leave this as non-zero is: if we are regularly switching
# the "queen peer" then we want to improve the chances that the new queen
# (formerly backfill) is idle and ready to serve urgent nodes.
# Another reason to leave this as non-zero: we don't want to overload the
# database with reads/writes, but there are probably better ways to acheive
# that goal.
# One reason to make it relatively short, is that we want to find out quickly
# when a new peer has excellent service stats. It might take several requests
# to establish it (partially because we measure using an exponential average).

# About how many seconds after a block can we request trie data from peers?
# The value is configurable by client, but tends to be around 120 blocks.
# To make up for clients that are configured low, unusually low block times,
# and other surprises, we pick half of the 15-second * 120 blocks time window:
ESTIMATED_BEAMABLE_SECONDS = 900

# We need MAX_UNCLE_DEPTH + 1 headers to check during uncle validation
# We need to request one more header, to set the starting tip
FULL_BLOCKS_NEEDED_TO_START_BEAM = MAX_UNCLE_DEPTH + 2
