class RPCModule:
    _chain = None

    def __init__(self, chain=None, p2p_server=None):
        self._chain = chain
        self._p2p_server = p2p_server

    def set_chain(self, chain):
        self._chain = chain
