import logging

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

from evm.chains.sharding.mainchain_handler.vmc_utils import (
    create_vmc_tx,
    get_contract_address_from_contract_tx,
    get_vmc_json,
)


class VMCHandler:

    logger = logging.getLogger("evm.chain.sharding.mainchain_handler.VMCHandler")

    def __init__(self, mainchain_handler, primary_addr, TransactionClass):
        """
        :param primary_addr: address in bytes
        """
        self.mainchain_handler = mainchain_handler
        self.primary_addr = primary_addr
        self.init_vmc_attributes(TransactionClass)
        self.setup_vmc_instance()

    def init_vmc_attributes(self, TransactionClass):
        vmc_tx = create_vmc_tx(TransactionClass, gasprice=GASPRICE)
        self.vmc_sender_addr = vmc_tx.sender
        self.vmc_addr = get_contract_address_from_contract_tx(vmc_tx)
        vmc_json = get_vmc_json()
        self.vmc_abi = vmc_json['abi']
        self.vmc_bytecode = vmc_json['bytecode']
        self.logger.debug("vmc_addr=%s", self.vmc_addr)
        self.logger.debug("vmc_sender_addr=%s", self.vmc_sender_addr)

    def setup_vmc_instance(self):
        self.vmc = self.mainchain_handler.contract(
            to_checksum_address(self.vmc_addr),
            self.vmc_abi,
            self.vmc_bytecode,
        )

    @to_dict
    def _mk_contract_tx_detail(self,
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
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_detail = self._mk_contract_tx_detail(sender_addr=sender_addr, gas=gas)
        address_in_hex = self.vmc.call(tx_detail).sample(shard_id)
        # TODO: should see if there is a better way to automatically change the address result from
        #       hex to bytes in. Maybe in `decode_contract_call_result`?
        return decode_hex(address_in_hex)

    def deposit(self,
                validation_code_addr,
                return_addr,
                sender_addr=None,
                gas=TX_GAS,
                gas_price=GASPRICE):
        """deposit(validation_code_addr: address, return_addr: address) -> num
        """
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_detail = self._mk_contract_tx_detail(
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
            value=DEPOSIT_SIZE,
        )
        validation_code_addr_hex = to_checksum_address(validation_code_addr)
        return_addr_hex = to_checksum_address(return_addr)
        tx_hash = self.vmc.transact(tx_detail).deposit(
            validation_code_addr_hex,
            return_addr_hex,
        )
        return tx_hash

    def withdraw(self, validator_index, sig, sender_addr=None, gas=TX_GAS, gas_price=GASPRICE):
        """withdraw(validator_index: num, sig: bytes <= 1000) -> bool
        """
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_detail = self._mk_contract_tx_detail(
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
        )
        tx_hash = self.vmc.transact(tx_detail).withdraw(
            validator_index,
            sig,
        )
        return tx_hash

    def get_shard_list(self, valcode_addr, sender_addr=None, gas=TX_GAS):
        """get_shard_list(valcode_addr: address) -> bool[100]
        """
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_detail = self._mk_contract_tx_detail(sender_addr=sender_addr, gas=gas)
        valcode_addr_hex = to_checksum_address(valcode_addr)
        return self.vmc.call(tx_detail).get_shard_list(valcode_addr_hex)

    def add_header(self, header, sender_addr=None, gas=TX_GAS, gas_price=GASPRICE):
        """add_header(header: bytes <= 4096) -> bool
        """
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_detail = self._mk_contract_tx_detail(
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
        )
        tx_hash = self.vmc.transact(tx_detail).add_header(header)
        return tx_hash

    def get_period_start_prevhash(self, expected_period_number, sender_addr=None, gas=TX_GAS):
        """get_period_start_prevhash(expected_period_number: num) -> bytes32
        """
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_detail = self._mk_contract_tx_detail(sender_addr=sender_addr, gas=gas)
        return self.vmc.call(tx_detail).get_period_start_prevhash(expected_period_number)

    def tx_to_shard(self,
                    to,
                    shard_id,
                    tx_startgas,
                    tx_gasprice,
                    data,
                    value,
                    sender_addr=None,
                    gas=TX_GAS,
                    gas_price=GASPRICE):
        """tx_to_shard(
            to: address, shard_id: num, tx_startgas: num, tx_gasprice: num, data: bytes <= 4096
           ) -> num
        """
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_detail = self._mk_contract_tx_detail(
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
            value=value,
        )
        to = to_checksum_address(to)
        tx_hash = self.vmc.transact(tx_detail).tx_to_shard(
            to,
            shard_id,
            tx_startgas,
            tx_gasprice,
            data,
        )
        return tx_hash

    def get_collation_gas_limit(self, sender_addr=None, gas=TX_GAS):
        """get_collation_gas_limit() -> num
        """
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_detail = self._mk_contract_tx_detail(sender_addr=sender_addr, gas=gas)
        return self.vmc.call(tx_detail).get_collation_gas_limit()

    def get_collation_header_score(self,
                                   shard_id,
                                   collation_header_hash,
                                   sender_addr=None,
                                   gas=TX_GAS):
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_detail = self._mk_contract_tx_detail(sender_addr=sender_addr, gas=gas)
        return self.vmc.call(tx_detail).get_collation_headers__score(
            shard_id,
            collation_header_hash,
        )

    def get_num_validators(self, sender_addr=None, gas=TX_GAS):
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_detail = self._mk_contract_tx_detail(sender_addr=sender_addr, gas=gas)
        return self.vmc.call(tx_detail).get_num_validators()

    def get_receipt_value(self, receipt_id, sender_addr=None, gas=TX_GAS):
        if sender_addr is None:
            sender_addr = self.primary_addr
        tx_detail = self._mk_contract_tx_detail(sender_addr=sender_addr, gas=gas)
        return self.vmc.call(tx_detail).get_receipts__value(receipt_id)
