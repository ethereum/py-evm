# If a peer returns 0 results, wait this many seconds before asking it for anything else
EMPTY_PEER_RESPONSE_PENALTY = 15.0

# Picked a reorg number that is covered by a single skeleton header request,
# which covers about 6 days at 15s blocks
MAX_SKELETON_REORG_DEPTH = 35000
