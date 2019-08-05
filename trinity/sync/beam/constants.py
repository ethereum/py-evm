# Peers are typically expected to have predicted nodes available,
#   so it's reasonable to ask for all-predictive nodes from a peer.
# Urgent node requests usually come in pretty fast, so
#   even at a small value (like 1ms), this timeout is rarely triggered.
DELAY_BEFORE_NON_URGENT_REQUEST = 0.001
