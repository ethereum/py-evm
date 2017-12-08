from eth_tester.exceptions import ValidationError

import eth_utils

from evm.utils.address import generate_contract_address

from viper import compiler

from config import (
    DEPOSIT_SIZE,
    GASPRICE,
    SHUFFLING_CYCLE_LENGTH,
    TX_GAS,
)

from vmc_utils import (
    decode_vmc_call_result,
    get_valmgr_addr,
    get_valmgr_bytecode,
    get_valmgr_code,
    get_valmgr_sender_addr,
    mk_initiating_contracts,
    mk_validation_code,
    mk_vmc_tx_obj,
)

class VMCHandler:

    def __init__(self, chain_handler, primary_addr):
        self.chain_handler = chain_handler
        self.primary_addr = primary_addr
        self.init_vmc_attributes()

    def init_vmc_attributes(self):
        self._vmc_addr = get_valmgr_addr()
        print("!@# vmc_addr={}".format(self._vmc_addr))
        self._vmc_sender_addr = get_valmgr_sender_addr()
        print("!@# vmc_sender_addr={}".format(self._vmc_sender_addr))
        self._vmc_bytecode = get_valmgr_bytecode()
        self._vmc_code = get_valmgr_code()
        self._vmc_abi = compiler.mk_full_signature(self._vmc_code)
        # print("!@# vmc_abi={}".format(self._vmc_abi))

    # vmc utils ####################################

    def call_vmc(
            self,
            func_name,
            args,
            sender_addr=None,
            value=0,
            gas=TX_GAS,
            gas_price=GASPRICE):
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_obj = mk_vmc_tx_obj(func_name, args, sender_addr, value, gas, gas_price)
        result = self.chain_handler.call(tx_obj)
        decoded_result = decode_vmc_call_result(func_name, result)
        print("!@# call_vmc: func_name={}, args={}, result={}".format(
            func_name,
            args,
            decoded_result,
        ))
        return decoded_result

    def send_vmc_tx(
            self,
            func_name,
            args,
            sender_addr=None,
            value=0,
            gas=TX_GAS,
            gas_price=GASPRICE):
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_obj = mk_vmc_tx_obj(func_name, args, sender_addr, value, gas, gas_price)
        tx_hash = self.chain_handler.send_transaction(tx_obj)
        print("!@# send_vmc_tx: func_name={}, args={}, tx_hash={}".format(
            func_name,
            args,
            tx_hash,
        ))
        return tx_hash

    # vmc related #############################

    def sample(self, shard_id, sender_addr=None):
        '''sample(shard_id: num) -> address
        '''
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.call_vmc('sample', [shard_id], sender_addr=sender_addr)

    def deposit(
            self,
            validation_code_addr,
            return_addr,
            sender_addr=None,
            gas=TX_GAS,
            gas_price=GASPRICE):
        '''deposit(validation_code_addr: address, return_addr: address) -> num
        '''
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.send_vmc_tx(
            'deposit',
            [validation_code_addr, return_addr],
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
            value=DEPOSIT_SIZE,
        )

    def withdraw(self, validator_index, sig, sender_addr=None, gas=TX_GAS, gas_price=GASPRICE):
        '''withdraw(validator_index: num, sig: bytes <= 1000) -> bool
        '''
        return self.send_vmc_tx(
            'withdraw',
            [validator_index, sig],
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
        )

    def get_shard_list(self, valcode_addr, sender_addr=None):
        '''get_shard_list(valcode_addr: address) -> bool[100]
        '''
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.call_vmc('get_shard_list', [valcode_addr], sender_addr=sender_addr)

    def add_header(self, header, sender_addr=None, gas=TX_GAS, gas_price=GASPRICE):
        '''add_header(header: bytes <= 4096) -> bool
        '''
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.send_vmc_tx(
            'add_header',
            [header],
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
        )

    def get_period_start_prevhash(self, expected_period_number, sender_addr=None):
        '''get_period_start_prevhash(expected_period_number: num) -> bytes32
        '''
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.call_vmc(
            'get_period_start_prevhash',
            [expected_period_number],
            sender_addr=sender_addr,
        )

    def tx_to_shard(
            self,
            to,
            shard_id,
            tx_startgas,
            tx_gasprice,
            data,
            value,
            sender_addr=None,
            gas=TX_GAS,
            gas_price=GASPRICE):
        '''tx_to_shard(
            to: address, shard_id: num, tx_startgas: num, tx_gasprice: num, data: bytes <= 4096
           ) -> num
        '''
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.send_vmc_tx(
            'tx_to_shard',
            [to, shard_id, tx_startgas, tx_gasprice, data],
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
            value=value,
        )

    def get_collation_gas_limit(self, sender_addr=None):
        '''get_collation_gas_limit() -> num
        '''
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.call_vmc('get_collation_gas_limit', [], sender_addr=sender_addr)

    def get_collation_header_score(self, shard_id, collation_header_hash, sender_addr=None):
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.call_vmc(
            'get_collation_headers__score',
            [shard_id, collation_header_hash],
            sender_addr=sender_addr,
        )

    def get_num_validators(self, sender_addr=None):
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.call_vmc('get_num_validators', [], sender_addr=sender_addr)

    def get_receipt_value(self, receipt_id, sender_addr=None):
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.call_vmc('get_receipts__value', [receipt_id], sender_addr=sender_addr)

    # utils #######################################################

    def is_vmc_deployed(self):
        return (
            # self.chain_handler.get_code(self._vmc_addr) != b'' and \
            self.chain_handler.get_nonce(self._vmc_sender_addr) != 0
        )

    def deploy_valcode_and_deposit(self, key):
        '''
        Deploy validation code of and with the key, and do deposit

        :param key: Key object
        :return: returns nothing
        '''
        address = key.public_key.to_checksum_address()
        self.chain_handler.unlock_account(address)
        valcode = mk_validation_code(
            key.public_key.to_canonical_address()
        )
        nonce = self.chain_handler.get_nonce(address)
        valcode_addr = eth_utils.address.to_checksum_address(
            generate_contract_address(eth_utils.to_canonical_address(address), nonce)
        )
        self.chain_handler.unlock_account(address)
        self.chain_handler.deploy_contract(valcode, address)
        self.chain_handler.mine(1)
        self.deposit(valcode_addr, address, address)

    def deploy_initiating_contracts(self, privkey):
        if not self.is_vmc_deployed():
            addr = privkey.public_key.to_checksum_address()
            self.chain_handler.unlock_account(addr)
            nonce = self.chain_handler.get_nonce(addr)
            txs = mk_initiating_contracts(privkey, nonce)
            for tx in txs[:3]:
                self.chain_handler.direct_tx(tx)
            self.chain_handler.mine(1)
            for tx in txs[3:]:
                self.chain_handler.direct_tx(tx)
                self.chain_handler.mine(1)
            print(
                '!@# deploy: vmc: ',
                self.chain_handler.get_transaction_receipt(eth_utils.encode_hex(txs[-1].hash)),
            )

    def first_setup_and_deposit(self, key):
        self.deploy_valcode_and_deposit(key)
        # TODO: error occurs when we don't mine so many blocks
        self.chain_handler.mine(SHUFFLING_CYCLE_LENGTH)

    def import_key_to_chain_handler(self, key):
        try:
            self.chain_handler.import_privkey(key.to_hex())
        except (ValueError, ValidationError):
            pass
