import time

import rlp

from eth_utils import (
    to_checksum_address,
)

from evm.chains.sharding.mainchain_handler.config import (
    GASPRICE,
    TX_GAS,
)


class MainchainHandler:

    def __init__(self, web3_instance):
        self.w3 = web3_instance
        assert self.w3.isConnected()

    # RPC related

    def get_block_by_number(self, block_number):
        return self.w3.eth.getBlock(block_number)

    def get_block_number(self):
        return self.w3.eth.blockNumber

    def get_code(self, address):
        address = to_checksum_address(address)
        return self.w3.eth.getCode(address)

    def get_nonce(self, address):
        address = to_checksum_address(address)
        return self.w3.eth.getTransactionCount(address)

    def mine(self, number):
        expected_block_number = self.get_block_number() + number
        self.w3.miner.start(1)
        while self.get_block_number() < expected_block_number:
            time.sleep(0.1)
        self.w3.miner.stop()

    def unlock_account(self, account, passphrase):
        account = to_checksum_address(account)
        self.w3.personal.unlockAccount(account, passphrase)

    def get_transaction_receipt(self, tx_hash):
        return self.w3.eth.getTransactionReceipt(tx_hash)

    def contract(self, contract_addr, abi, bytecode):
        contract_addr = to_checksum_address(contract_addr)
        return self.w3.eth.contract(contract_addr, abi=abi, bytecode=bytecode)

    def send_transaction(self, tx_obj):
        return self.w3.eth.sendTransaction(tx_obj)

    def call(self, tx_obj):
        return self.w3.eth.call(tx_obj)

    # utils

    def deploy_contract(self, bytecode, address, value=0, gas=TX_GAS, gas_price=GASPRICE):
        address = to_checksum_address(address)
        tx_hash = self.send_transaction({
            'from': address,
            'value': value,
            'gas': gas,
            'gas_price': gas_price,
            'data': bytecode,
        })
        return tx_hash

    def direct_tx(self, tx):
        raw_tx = rlp.encode(tx)
        raw_tx_hex = self.w3.toHex(raw_tx)
        tx_hash = self.w3.eth.sendRawTransaction(raw_tx_hex)
        return tx_hash
