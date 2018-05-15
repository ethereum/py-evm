from evm.db.backends.base import BaseDB


class KeyMapDB(BaseDB):
    """
    Modify keys when accessing the database, accourding to the
    keymap function set at initialization.
    """
    def __init__(self, keymap, db):
        self._keymap = keymap
        self._db = db

    def __getitem__(self, key):
        mapped_key = self._keymap(key)
        return self._db[mapped_key]

    def __setitem__(self, key, val):
        mapped_key = self._keymap(key)
        self._db[mapped_key] = val

    def __delitem__(self, key):
        mapped_key = self._keymap(key)
        del self._db[mapped_key]

    def __contains__(self, key):
        mapped_key = self._keymap(key)
        return mapped_key in self._db

    def __getattr__(self, attr):
        return getattr(self._db, attr)

    def __setattr__(self, attr, val):
        if attr in ('_db', '_keymap'):
            super().__setattr__(attr, val)
        else:
            setattr(self._db, attr, val)
