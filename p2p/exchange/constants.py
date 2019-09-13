# The default timeout for a round trip API request and response from a peer.
#
# > NOTE: This value **MUST** be less than `p2p.constants.CONN_IDLE_TIMEOUT` for
# it to be meaningful.  Otherwise, the actual reading of the p2p message from
# the network will timeout before this timeout is ever hit.
ROUND_TRIP_TIMEOUT = 20.0


# We send requests to peers one at a time, but might initiate a few locally before
# they are sent. This is an estimate of how many get queued locally. The reason we
# estimate the queue length is to determine how long a timeout to use when
# waiting for the lock to send the next queued peer request.
NUM_QUEUED_REQUESTS = 3
