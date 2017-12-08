from evm.chains.sharding.mainchain_handler.config import (
    GASPRICE,
    PASSPHRASE,
    TX_GAS,
)

class BaseChainHandler:

    # RPC related

    def get_block_by_number(self, block_number):
        raise NotImplementedError("Must be implemented by subclasses")

    def get_block_number(self):
        raise NotImplementedError("Must be implemented by subclasses")

    def get_nonce(self, address):
        raise NotImplementedError("Must be implemented by subclasses")

    def import_privkey(self, privkey, passphrase=PASSPHRASE):
        raise NotImplementedError("Must be implemented by subclasses")

    def mine(self, number):
        raise NotImplementedError("Must be implemented by subclasses")

    def unlock_account(self, account, passphrase=PASSPHRASE):
        raise NotImplementedError("Must be implemented by subclasses")

    def get_transaction_receipt(self, tx_hash):
        raise NotImplementedError("Must be implemented by subclasses")

    def send_transaction(self, tx_obj):
        raise NotImplementedError("Must be implemented by subclasses")

    def call(self, tx_obj):
        raise NotImplementedError("Must be implemented by subclasses")

    # utils

    def deploy_contract(self, bytecode, address, value=0, gas=TX_GAS, gas_price=GASPRICE):
        raise NotImplementedError("Must be implemented by subclasses")

    def direct_tx(self, tx):
        raise NotImplementedError("Must be implemented by subclasses")
