import logging

from eth_utils import (
    to_canonical_address,
    to_checksum_address,
    to_dict,
)

from evm.chains.sharding.mainchain_handler.config import (
    DEPOSIT_SIZE,
    GASPRICE,
    TX_GAS,
)

from evm.chains.sharding.mainchain_handler.vmc_utils import (
    get_valmgr_abi,
    get_valmgr_addr,
    get_valmgr_bytecode,
    get_valmgr_code,
    get_valmgr_sender_addr,
)

class VMCHandler:

    logger = logging.getLogger("evm.chain.sharding.mainchain_handler.VMCHandler")

    def __init__(self, mainchain_handler, primary_addr):
        """
        :param primary_addr: address in bytes
        """
        self.mainchain_handler = mainchain_handler
        self.primary_addr = primary_addr
        self.init_vmc_attributes()
        self.setup_vmc_instance()

    def init_vmc_attributes(self):
        self._vmc_addr = get_valmgr_addr()
        self._vmc_sender_addr = get_valmgr_sender_addr()
        self._vmc_bytecode = get_valmgr_bytecode()
        self._vmc_code = get_valmgr_code()
        self._vmc_abi = get_valmgr_abi()
        self.logger.debug("vmc_addr=%s", self._vmc_addr)
        self.logger.debug("vmc_sender_addr=%s", self._vmc_sender_addr)

    def setup_vmc_instance(self):
        self._vmc = self.mainchain_handler.contract(
            to_checksum_address(self._vmc_addr),
            self._vmc_abi,
            self._vmc_bytecode,
        )

    # vmc utils ####################################

    @property
    def vmc(self):
        return self.get_vmc()

    def get_vmc(self):
        """
        :return: web3.eth.contract instance of vmc
        """
        return self._vmc

    @to_dict
    def _mk_contract_tx_detail(self, sender_addr, gas, value=None, gas_price=None):
        # Both 'from' and 'gas' are required in eth_tester
        if sender_addr is None:
            raise ValueError('sender_addr should not be None')
        if gas is None:
            raise ValueError('gas should not be None')
        yield 'from', to_checksum_address(sender_addr)
        yield 'gas', gas
        if value is not None:
            yield 'value', value
        if gas_price is not None:
            yield 'gas_price', gas_price

    def call_vmc(self,
                 func_name,
                 args,
                 sender_addr=None,
                 value=0,
                 gas=TX_GAS,
                 gas_price=GASPRICE):
        if sender_addr is None:
            sender_addr = self.primary_addr
        sender_addr = to_checksum_address(sender_addr)
        contract_tx_detail = self._mk_contract_tx_detail(
            sender_addr=sender_addr,
            gas=gas,
            value=value,
            gas_price=gas_price,
        )
        caller = self.vmc.call(contract_tx_detail)
        result = getattr(caller, func_name)(*args)
        self.logger.debug(
            "call_vmc: func_name=%s, args=%s, result=%s",
            func_name,
            args,
            result,
        )
        return result

    def send_vmc_tx(self,
                    func_name,
                    args,
                    sender_addr=None,
                    value=0,
                    gas=TX_GAS,
                    gas_price=GASPRICE):
        if sender_addr is None:
            sender_addr = self.primary_addr
        sender_addr = to_checksum_address(sender_addr)
        contract_tx_detail = self._mk_contract_tx_detail(
            sender_addr=sender_addr,
            gas=gas,
            value=value,
            gas_price=gas_price,
        )
        caller = self.vmc.transact(contract_tx_detail)
        tx_hash = getattr(caller, func_name)(*args)
        self.logger.debug(
            "send_vmc_tx: func_name=%s, args=%s, tx_hash=%s",
            func_name,
            args,
            tx_hash,
        )
        return tx_hash

    # vmc related #############################

    def sample(self, shard_id, sender_addr=None):
        """sample(shard_id: num) -> address
        """
        if sender_addr is None:
            sender_addr = self.primary_addr
        address_in_hex = self.call_vmc('sample', [shard_id], sender_addr=sender_addr)
        # TODO: should see if there is a better way to automatically change the address result from
        #       hex to bytes in. Maybe in `decode_contract_call_result`?
        return to_canonical_address(address_in_hex)

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
        validation_code_addr_hex = to_checksum_address(validation_code_addr)
        return_addr_hex = to_checksum_address(return_addr)
        return self.send_vmc_tx(
            'deposit',
            [validation_code_addr_hex, return_addr_hex],
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
            value=DEPOSIT_SIZE,
        )

    def withdraw(self, validator_index, sig, sender_addr=None, gas=TX_GAS, gas_price=GASPRICE):
        """withdraw(validator_index: num, sig: bytes <= 1000) -> bool
        """
        return self.send_vmc_tx(
            'withdraw',
            [validator_index, sig],
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
        )

    def get_shard_list(self, valcode_addr, sender_addr=None):
        """get_shard_list(valcode_addr: address) -> bool[100]
        """
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.call_vmc('get_shard_list', [valcode_addr], sender_addr=sender_addr)

    def add_header(self, header, sender_addr=None, gas=TX_GAS, gas_price=GASPRICE):
        """add_header(header: bytes <= 4096) -> bool
        """
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
        """get_period_start_prevhash(expected_period_number: num) -> bytes32
        """
        if sender_addr is None:
            sender_addr = self.primary_addr
        return self.call_vmc(
            'get_period_start_prevhash',
            [expected_period_number],
            sender_addr=sender_addr,
        )

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
        to = to_checksum_address(to)
        return self.send_vmc_tx(
            'tx_to_shard',
            [to, shard_id, tx_startgas, tx_gasprice, data],
            sender_addr=sender_addr,
            gas=gas,
            gas_price=gas_price,
            value=value,
        )

    def get_collation_gas_limit(self, sender_addr=None):
        """get_collation_gas_limit() -> num
        """
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
            self.mainchain_handler.get_code(self._vmc_addr) != b'' and \
            self.mainchain_handler.get_nonce(self._vmc_sender_addr) != 0
        )
