"""Provide access to the local database via a ChainDB instance.

Run with `python -i db-shell.py` to get an interactive shell with a ChainDB instance available
as `chaindb`.

By default it will use the mainnet full DB.
"""
import argparse

from eth_utils import encode_hex

from eth.db.chain import ChainDB
from eth.db.backends.level import LevelDB

from trinity.config import TrinityConfig
from trinity.constants import (
    MAINNET_NETWORK_ID,
    ROPSTEN_NETWORK_ID,
    SYNC_FULL,
    SYNC_FAST,
    SYNC_LIGHT,
)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-ropsten', action='store_true')
    parser.add_argument('-light', action='store_true')
    args = parser.parse_args()

    network_id = MAINNET_NETWORK_ID
    if args.ropsten:
        network_id = ROPSTEN_NETWORK_ID

    if args.light:
        sync_mode = SYNC_LIGHT
    elif args.full:
        sync_mode = SYNC_FULL
    else:
        sync_mode = SYNC_FAST

    cfg = TrinityConfig(network_id, sync_mode=sync_mode)
    chaindb = ChainDB(LevelDB(cfg.database_dir))
    head = chaindb.get_canonical_head()
    print("Head #%d; hash: %s, state_root: %s" % (
          head.block_number, head.hex_hash, encode_hex(head.state_root)))
