from contextlib import contextmanager


class BaseState(object):
    chaindb = None
    block = None

    def __init__(self, chaindb, block):
        self.chaindb = chaindb
        self.block = block

    @contextmanager
    def state_db(self, read_only=False):
        state = self.chaindb.get_state_db(self.block.header.state_root, read_only)
        yield state

        if read_only:
            # This acts as a secondary check that no mutation took place for
            # read_only databases.
            assert state.root_hash == self.block.header.state_root
        elif self.block.header.state_root != state.root_hash:
            self.block.header.state_root = state.root_hash

        # remove the reference to the underlying `db` object to ensure that no
        # further modifications can occur using the `State` object after
        # leaving the context.
        state.db = None
        state._trie = None

    @classmethod
    def create_state(cls, chaindb, block):
        return BaseState(chaindb, block)
