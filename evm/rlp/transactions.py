import rlp


class BaseTransaction(rlp.Serializable):
    @property
    def sender(self):
        return self.get_sender()

    def get_sender(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def intrensic_gas(self):
        return self.get_intrensic_gas()

    def get_intrensic_gas(self):
        raise NotImplementedError("Must be implemented by subclasses")

    def as_unsigned_transaction(self):
        raise NotImplementedError("Must be implemented by subclasses")


class BaseUnsignedTransaction(rlp.Serializable):
    def as_signed_transaction(self, private_key):
        raise NotImplementedError("Must be implemented by subclasses")
