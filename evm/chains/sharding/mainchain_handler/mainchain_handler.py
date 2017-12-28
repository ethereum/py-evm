import time

import rlp

from eth_utils import (
    encode_hex,
    to_checksum_address,
)

from evm.chains.sharding.mainchain_handler.config import (
    GASPRICE,
    TX_GAS,
)


class MainchainHandler:

    def __init__(self, w3):
        self.w3 = w3
        assert self.w3.isConnected()

    # RPC related

    def get_block_by_number(self, block_number):
        return self.w3.eth.getBlock(block_number)

    def get_block_number(self):
        return self.w3.eth.blockNumber

    def get_code(self, address):
        return self.w3.eth.getCode(to_checksum_address(address))

    def get_nonce(self, address):
        return self.w3.eth.getTransactionCount(to_checksum_address(address))

    def mine(self, number):
        expected_block_number = self.get_block_number() + number
        self.w3.miner.start(1)
        while self.get_block_number() < expected_block_number:
            time.sleep(0.1)
        self.w3.miner.stop()

    def get_transaction_receipt(self, tx_hash):
        return self.w3.eth.getTransactionReceipt(tx_hash)

    def contract(self, contract_addr, abi, bytecode):
        return self.w3.eth.contract(
            to_checksum_address(contract_addr),
            abi=abi,
            bytecode=bytecode,
        )

    def send_transaction(self, tx_obj):
        return self.w3.eth.sendTransaction(tx_obj)

    def call(self, tx_obj):
        return self.w3.eth.call(tx_obj)

    # utils

    def deploy_contract(self, bytecode, privkey, value=0, gas=TX_GAS, gas_price=GASPRICE):
        contract_transaction_dict = {
            'nonce': self.get_nonce(privkey.public_key.to_canonical_address()),
            'to': b'',  # CREATE_CONTRACT_ADDRESS
            'data': encode_hex(bytecode),
            'value': value,
            'gas': gas,
            'gasPrice': gas_price,
            'chainId': None,
        }
        signed_transaction_dict = self.w3.eth.account.signTransaction(
            contract_transaction_dict,
            privkey.to_hex(),
        )
        tx_hash = self.w3.eth.sendRawTransaction(signed_transaction_dict['rawTransaction'])
        return tx_hash

    def direct_tx(self, tx):
        raw_tx = rlp.encode(tx)
        raw_tx_hex = self.w3.toHex(raw_tx)
        tx_hash = self.w3.eth.sendRawTransaction(raw_tx_hex)
        return tx_hash
