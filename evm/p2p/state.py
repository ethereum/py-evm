import rlp

from trie.sync import HexaryTrieSync

from evm.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
)
from evm.rlp.accounts import Account


class StateSync(HexaryTrieSync):

    def leaf_callback(self, data, parent):
        # TODO: Need to figure out why geth uses 64 as the depth here, and then document it.
        depth = 64
        account = rlp.decode(data, sedes=Account)
        if account.storage_root != BLANK_ROOT_HASH:
            self.schedule(account.storage_root, parent, depth, leaf_callback=None)
        if account.code_hash != EMPTY_SHA3:
            self.schedule(account.code_hash, parent, depth, leaf_callback=None, is_raw=True)
