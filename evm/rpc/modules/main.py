class RPCModule:
    def __init__(self, chain=None):
        self._chain = chain

    @property
    def chain(self):
        return self._chain

    @chain.setter
    def chain(self, new_chain):
        self._chain = new_chain
