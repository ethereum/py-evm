class BaseMachineStorage(object):
    """
    Base class which implements the storage API.
    """
    #
    # Account storage methods
    #
    def set_storage(self, account, slot, value):
        raise NotImplementedError("The `set_storage` method is not implemented")

    def get_storage(self, account, slot):
        raise NotImplementedError("The `get_storage` method is not implemented")

    def delete_storage(self, account):
        raise NotImplementedError("The `delete_storage` method is not implemented")

    def set_balance(self, account, balance):
        raise NotImplementedError("The `set_balance` method is not implemented")

    def get_balance(self, account):
        raise NotImplementedError("The `get_balance` method is not implemented")

    def set_nonce(self, account, nonce):
        raise NotImplementedError("The `set_nonce` method is not implemented")

    def get_nonce(self, account):
        raise NotImplementedError("The `get_nonce` method is not implemented")

    def set_code(self, account, code):
        raise NotImplementedError("The `set_code` method is not implemented")

    def get_code(self, account):
        raise NotImplementedError("The `get_code` method is not implemented")

    def delete_code(self, account):
        raise NotImplementedError("The `delete_code` method is not implemented")

    #
    # Chain Storage
    #
    def get_block_hash(self, block_number):
        raise NotImplementedError("The `delete_code` method is not implemented")

    #
    # Account Helper Methods
    #
    def account_exists(self, account):
        raise NotImplementedError("The `delete_code` method is not implemented")

    #
    # Snapshoting and Restore
    #
    def snapshot(self):
        raise NotImplementedError("The `snapshot` method is not implemented")

    def revert(self, snapshot):
        raise NotImplementedError("The `revert` method is not implemented")
