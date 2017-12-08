from .backends.base import BaseDB


class TrackedDB(BaseDB):
    """
    The StateDB would be responsible for collecting all the touched keys.

    reads: the dict of read key-value
    writes: the dict of written key-value
    """

    wrapped_db = None
    _reads = None
    _writes = None

    def __init__(self, db):
        self.wrapped_db = db
        self._reads = {}
        self._writes = {}

    def get(self, key):
        """
        Return the value of specific key and update read dict.
        """
        try:
            current_value = self.wrapped_db.get(key)
        except KeyError:
            raise
        else:
            self._reads[key] = current_value

        return current_value

    def set(self, key, value):
        """
        Set the key-value and update writes dict.
        """
        self._writes[key] = value
        return self.wrapped_db.set(key, value)

    def exists(self, key):
        """
        Check if the key exsits.
        """
        return self.wrapped_db.exists(key)

    def delete(self, key):
        """
        Delete the key and update writes dict.
        """
        try:
            current_value = self.wrapped_db.get(key)
        except KeyError:
            # do not need to be added in writes
            pass
        else:
            self._writes[key] = current_value

        return self.wrapped_db.delete(key)

    def get_reads(self, key=None):
        """
        Return the whole or the specific value of reads dict.
        """
        if key is None:
            return self._reads
        else:
            return self._reads[key] if key in self._reads else None

    def get_writes(self, key=None):
        """
        Return the whole or the specific value of writes dict.
        """
        if key is None:
            return self._writes
        else:
            return self._writes[key] if key in self._writes else None

    def clear_log(self):
        """
        Clear reads and writes dicts.
        """
        self._reads = {}
        self._writes = {}
