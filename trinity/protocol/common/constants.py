# The default timeout for a round trip API request and response from a peer.
ROUND_TRIP_TIMEOUT = 20.0

# Timeout used when performing the check to ensure peers are on the same side of chain splits as
# us.
CHAIN_SPLIT_CHECK_TIMEOUT = 15


# We send requests to peers one at a time, but might initiate a few locally before
# they are sent. This is an estimate of how many get queued locally. The reason we
# estimate the queue length is to determine how long a timeout to use when
# waiting for the lock to send the next queued peer request.
NUM_QUEUED_REQUESTS = 3
