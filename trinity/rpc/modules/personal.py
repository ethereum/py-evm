from cytoolz import (
    identity,
)

from eth_utils import (
    decode_hex,
    encode_hex,
    int_to_big_endian,
    is_integer,
)

from trinity.rpc.format import (

    format_params,
    to_int_if_hex)

from trinity.rpc.modules import RPCModule


class Personal(RPCModule):
    '''
    All the methods defined by JSON-RPC API, starting with "personal"...
    '''

    def listAccounts(self):
        raise NotImplementedError()

    @format_params(decode_hex, identity)
    def importRawKey(self, private_key, passphrase):
        raise NotImplementedError()

    @format_params(identity)
    def newAccount(self, password):
        raise NotImplementedError()

    @format_params(decode_hex)
    def lockAccount(self, account):
        raise NotImplementedError()

    @format_params(decode_hex, identity, to_int_if_hex)
    def unlockAccount(self, account, passphrase, duration=None):
        raise NotImplementedError()

    @format_params(decode_hex, identity)
    def sendTransaction(self, transaction, passphrase):
        raise NotImplementedError()
