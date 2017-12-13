

class RPCModule:
    def __init__(self, chain):
        self._chain = chain

    def set_chain(self, new_chain):
        self._chain = new_chain
