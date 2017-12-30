import logging

from web3.contract import (
    Contract,
)

from eth_utils import (
    is_canonical_address,
    to_checksum_address,
    to_dict,
)

from evm.utils.hexadecimal import (
    decode_hex,
)

from evm.chains.sharding.mainchain_handler.config import (
    DEPOSIT_SIZE,
    GASPRICE,
    TX_GAS,
)


class VMC(Contract):

    logger = logging.getLogger("evm.chain.sharding.mainchain_handler.VMC")

    def __init__(self, *args, default_privkey, **kwargs):
        self.default_privkey = default_privkey
        self.default_sender_address = default_privkey.public_key.to_canonical_address()
        super().__init__(*args, **kwargs)

    @to_dict
    def mk_build_transaction_detail(self,
                                    nonce,
                                    gas,
                                    chain_id=None,
                                    value=None,
                                    gas_price=None,
                                    data=None):
        if not (isinstance(nonce, int) and nonce >= 0):
            raise ValueError('nonce should be provided as non-negative integer')
        if not (isinstance(gas, int) and gas > 0):
            raise ValueError('gas should be provided as positive integer')
        yield 'nonce', nonce
        yield 'gas', gas
        yield 'chainId', chain_id
        if value is not None:
            yield 'value', value
        if gas_price is not None:
            yield 'gasPrice', gas_price
        if data is not None:
            yield 'data', data

    def send_transaction(self,
                         func_name,
                         args,
                         nonce=None,
                         chain_id=None,
                         gas=TX_GAS,
                         value=0,
                         gas_price=GASPRICE,
                         data=None):
        privkey = self.default_privkey
        if nonce is None:
            nonce = self.web3.eth.getTransactionCount(privkey.public_key.to_checksum_address())
        build_transaction_detail = self.mk_build_transaction_detail(
            nonce=nonce,
            gas=gas,
            chain_id=chain_id,
            value=value,
            gas_price=gas_price,
            data=data,
        )
        build_transaction_instance = self.buildTransaction(build_transaction_detail)
        func_instance = getattr(build_transaction_instance, func_name)
        unsigned_transaction = func_instance(*args)
        signed_transaction_dict = self.web3.eth.account.signTransaction(
            unsigned_transaction,
            privkey.to_hex(),
        )
        tx_hash = self.web3.eth.sendRawTransaction(signed_transaction_dict['rawTransaction'])
        return tx_hash

    @to_dict
    def mk_contract_tx_detail(self,
                              sender_address,
                              gas,
                              value=None,
                              gas_price=None,
                              data=None):
        # Both 'from' and 'gas' are required in eth_tester
        if not is_canonical_address(sender_address):
            raise ValueError('sender_address should be provided in the canonical format')
        if not (isinstance(gas, int) and gas > 0):
            raise ValueError('gas should be provided as positive integer')
        yield 'from', to_checksum_address(sender_address)
        yield 'gas', gas
        if value is not None:
            yield 'value', value
        if gas_price is not None:
            yield 'gas_price', gas_price
        if data is not None:
            yield 'data', data

    # contract calls ##############################################

    def sample(self, shard_id, gas=TX_GAS):
        """sample(shard_id: num) -> address
        """
        tx_detail = self.mk_contract_tx_detail(sender_address=self.default_sender_address, gas=gas)
        address_in_hex = self.call(tx_detail).sample(shard_id)
        return decode_hex(address_in_hex)

    def deposit(self,
                validation_code_addr,
                return_addr,
                gas=TX_GAS,
                gas_price=GASPRICE):
        """deposit(validation_code_addr: address, return_addr: address) -> num
        """
        tx_hash = self.send_transaction(
            'deposit',
            [
                to_checksum_address(validation_code_addr),
                to_checksum_address(return_addr),
            ],
            value=DEPOSIT_SIZE,
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def withdraw(self, validator_index, sig, gas=TX_GAS, gas_price=GASPRICE):
        """withdraw(validator_index: num, sig: bytes <= 1000) -> bool
        """
        tx_hash = self.send_transaction(
            'withdraw',
            [
                validator_index,
                sig,
            ],
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def add_header(self, header, gas=TX_GAS, gas_price=GASPRICE):
        """add_header(header: bytes <= 4096) -> bool
        """
        tx_hash = self.send_transaction(
            'add_header',
            [header],
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def tx_to_shard(self,
                    to,
                    shard_id,
                    tx_startgas,
                    tx_gasprice,
                    data,
                    value,
                    gas=TX_GAS,
                    gas_price=GASPRICE):
        """tx_to_shard(
            to: address, shard_id: num, tx_startgas: num, tx_gasprice: num, data: bytes <= 4096
           ) -> num
        """
        tx_hash = self.send_transaction(
            'tx_to_shard',
            [
                to_checksum_address(to),
                shard_id,
                tx_startgas,
                tx_gasprice,
                data,
            ],
            value=value,
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash
