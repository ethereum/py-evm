# How old (in seconds) must our local head be to cause us to start with a
# fast-sync before we switch to regular-sync.
#FAST_SYNC_CUTOFF = 60 * 60 * 24
FAST_SYNC_CUTOFF = 60


# How many blocks should we wait before updating the state root which the state
# syncer is syncing against.  This is anchored to the `--trie-cache-gens` default
# in geth.
STALE_STATE_ROOT_AGE = 120
