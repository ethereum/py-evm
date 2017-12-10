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

    @property
    def reads(self):
        return self._reads

    @property
    def writes(self):
        return self._writes

    def get(self, key):
        """
        Return the value of specific key and update read dict.
        """
        current_value = self.wrapped_db.get(key)
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
        result = self.wrapped_db.exists(key)
        self._reads[key] = self.wrapped_db.get(key) if result else None
        return result

    def delete(self, key):
        """
        Delete the key and update writes dict.
        """
        result = self.wrapped_db.delete(key)
        self._writes[key] = None
        return result
