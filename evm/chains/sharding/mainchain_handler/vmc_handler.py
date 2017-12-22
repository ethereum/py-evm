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

    @to_dict
    def mk_contract_tx_detail(self,
                              sender_addr,
                              gas,
                              value=None,
                              gas_price=None,
                              data=None):
        # Both 'from' and 'gas' are required in eth_tester
        if not is_canonical_address(sender_addr):
            raise ValueError('sender_addr should be provided in the canonical format')
        if not (isinstance(gas, int) and gas > 0):
            raise ValueError('gas should be provided as positive integer')
        yield 'from', to_checksum_address(sender_addr)
        yield 'gas', gas
        if value is not None:
            yield 'value', value
        if gas_price is not None:
            yield 'gas_price', gas_price
        if data is not None:
            yield 'data', data

    # contract calls ##############################################

    def sample(self, shard_id, sender_addr=None, gas=TX_GAS):
        """sample(shard_id: num) -> address
        """
        tx_detail = self.mk_contract_tx_detail(sender_addr=sender_addr, gas=gas)
        address_in_hex = self.call(tx_detail).sample(shard_id)
        return decode_hex(address_in_hex)

    def deposit(self,
                validation_code_addr,
                return_addr,
                sender_addr,
                gas=TX_GAS,
                gas_price=GASPRICE):
        """deposit(validation_code_addr: address, return_addr: address) -> num
        """
        tx_detail = self.mk_contract_tx_detail(
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
            value=DEPOSIT_SIZE,
        )
        validation_code_addr_hex = to_checksum_address(validation_code_addr)
        return_addr_hex = to_checksum_address(return_addr)
        tx_hash = self.transact(tx_detail).deposit(
            validation_code_addr_hex,
            return_addr_hex,
        )
        return tx_hash

    def withdraw(self, validator_index, sig, sender_addr, gas=TX_GAS, gas_price=GASPRICE):
        """withdraw(validator_index: num, sig: bytes <= 1000) -> bool
        """
        tx_detail = self.mk_contract_tx_detail(
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
        )
        tx_hash = self.transact(tx_detail).withdraw(
            validator_index,
            sig,
        )
        return tx_hash

    def add_header(self, header, sender_addr, gas=TX_GAS, gas_price=GASPRICE):
        """add_header(header: bytes <= 4096) -> bool
        """
        tx_detail = self.mk_contract_tx_detail(
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
        )
        tx_hash = self.transact(tx_detail).add_header(header)
        return tx_hash

    def tx_to_shard(self,
                    to,
                    shard_id,
                    tx_startgas,
                    tx_gasprice,
                    data,
                    value,
                    sender_addr,
                    gas=TX_GAS,
                    gas_price=GASPRICE):
        """tx_to_shard(
            to: address, shard_id: num, tx_startgas: num, tx_gasprice: num, data: bytes <= 4096
           ) -> num
        """
        tx_detail = self.mk_contract_tx_detail(
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
            value=value,
        )
        to = to_checksum_address(to)
        tx_hash = self.transact(tx_detail).tx_to_shard(
            to,
            shard_id,
            tx_startgas,
            tx_gasprice,
            data,
        )
        return tx_hash
