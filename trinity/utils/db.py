class MemoryDB:
    kv_store = None

    def __init__(self, kv_store=None):
        if kv_store is None:
            self.kv_store = {}
        else:
            self.kv_store = kv_store

    def get(self, key):
        return self.kv_store[key]

    def set(self, key, value):
        self.kv_store[key] = value

    def exists(self, key):
        return key in self.kv_store

    def delete(self, key):
        del self.kv_store[key]

    #
    # Dictionary API
    #
    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def __delitem__(self, key):
        return self.delete(key)

    def __contains__(self, key):
        return self.exists(key)
