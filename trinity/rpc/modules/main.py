class RPCModule:
    _chain = None

    def __init__(self, chain=None):
        self._chain = chain

    def set_chain(self, chain):
        self._chain = chain
