class BaseMachineStorage(object):
    """
    Base class which implements the storage API.
    """
    def set_storage(self, account, slot, value):
        raise NotImplementedError("The `set_storage` method is not implemented")

    def get_storage(self, account, slot):
        raise NotImplementedError("The `set_storage` method is not implemented")

    def set_balance(self, account, balance):
        raise NotImplementedError("The `set_storage` method is not implemented")

    def get_balance(self, account):
        raise NotImplementedError("The `set_storage` method is not implemented")

    def set_nonce(self, account, nonce):
        raise NotImplementedError("The `set_storage` method is not implemented")

    def get_nonce(self, account):
        raise NotImplementedError("The `set_storage` method is not implemented")

    def set_code(self, account, code):
        raise NotImplementedError("The `set_storage` method is not implemented")

    def get_code(self, account):
        raise NotImplementedError("The `set_storage` method is not implemented")
