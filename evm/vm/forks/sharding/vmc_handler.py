import logging

from cytoolz import (
    pipe,
)

import rlp

from web3.contract import (
    Contract,
)

from eth_utils import (
    is_canonical_address,
    to_checksum_address,
    to_dict,
    to_tuple,
)

from evm.rlp.sedes import (
    address,
    hash32,
)

from evm.utils.hexadecimal import (
    decode_hex,
)
from evm.utils.keccak import (
    keccak,
)
from evm.utils.numeric import (
    big_endian_to_int,
)

from evm.vm.forks.sharding.config import (
    get_sharding_config,
)


class NextLogUnavailable(Exception):
    pass


class FilterNotFound(Exception):
    pass


class VMC(Contract):

    logger = logging.getLogger("evm.chain.sharding.mainchain_handler.VMC")

    # For handling logs filtering
    # Event:
    #   CollationAdded(indexed uint256 shard, bytes collationHeader, bool isNewHead, uint256 score)
    collation_added_topic = "0x" + keccak(b"CollationAdded(int128,bytes4096,bool,int128)").hex()
    new_collation_added_logs = {}
    # newer <---------------> older
    unchecked_collation_added_logs = {}
    collation_added_filter = {}
    current_checking_score = {}

    def __init__(self, *args, default_privkey, **kwargs):
        self.default_privkey = default_privkey
        self.default_sender_address = default_privkey.public_key.to_canonical_address()
        self.config = get_sharding_config()
        super().__init__(*args, **kwargs)

    def setup_collation_added_filter(self, shard_id):
        shard_id_topic = "0x" + shard_id.to_bytes(32, byteorder='big').hex()
        self.collation_added_filter[shard_id] = self.web3.eth.filter({
            'address': self.address,
            'topics': [
                self.collation_added_topic,
                shard_id_topic,
            ],
        })
        self.new_collation_added_logs[shard_id] = []
        self.unchecked_collation_added_logs[shard_id] = []
        self.current_checking_score[shard_id] = None

    @to_dict
    def parse_collation_added_data(self, data):
        score = big_endian_to_int(data[-32:])
        is_new_head = bool(big_endian_to_int(data[-64:-32]))
        header_bytes = data[:-64]
        # [num, num, bytes32, bytes32, bytes32, address, bytes32, bytes32, num, bytes]
        sedes = rlp.sedes.List([
            rlp.sedes.big_endian_int,
            rlp.sedes.big_endian_int,
            hash32,
            hash32,
            hash32,
            address,
            hash32,
            hash32,
            rlp.sedes.big_endian_int,
            rlp.sedes.binary,
        ])
        header_values = rlp.decode(header_bytes, sedes=sedes)
        yield 'header', header_values
        yield 'is_new_head', is_new_head
        yield 'score', score

    @to_tuple
    def _get_new_logs(self, shard_id):
        # use `get_new_entries` over `get_all_entries`
        #   1. Prevent from the increasing size of logs
        #   2. Leave the efforts maintaining `new_logs` in RPC servers
        if shard_id not in self.collation_added_filter:
            raise FilterNotFound(
                "CollationAdded filter haven't been set up in shard {}".format(shard_id)
            )
        new_logs = self.collation_added_filter[shard_id].get_new_entries()
        for log in new_logs:
            yield pipe(
                log['data'],
                decode_hex,
                self.parse_collation_added_data,
            )

    def get_next_log(self, shard_id):
        new_logs = self._get_new_logs(shard_id)
        self.new_collation_added_logs[shard_id] += new_logs
        if self.new_collation_added_logs[shard_id] == []:
            raise NextLogUnavailable("No more next logs")
        return self.new_collation_added_logs[shard_id].pop()

    def fetch_candidate_head(self, shard_id):
        # Try to return a log that has the score that we are checking for,
        # checking in order of oldest to most recent.
        for i in range(len(self.unchecked_collation_added_logs[shard_id]) - 1, -1, -1):
            if self.unchecked_collation_added_logs[shard_id][i]['score'] == \
               self.current_checking_score[shard_id]:
                return self.unchecked_collation_added_logs[shard_id].pop(i)
        # If no further recorded but unchecked logs exist, go to the next
        # is_new_head = true log
        while True:
            # TODO: currently just raise when there is no log anymore
            self.unchecked_collation_added_logs[shard_id].append(self.get_next_log(shard_id))
            if self.unchecked_collation_added_logs[shard_id][-1]['is_new_head'] is True:
                break
        log = self.unchecked_collation_added_logs[shard_id].pop()
        self.current_checking_score[shard_id] = log['score']
        return log

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
                         gas=None,
                         value=0,
                         gas_price=None,
                         data=None):
        if gas is None:
            gas = self.config['DEFAULT_GAS']
        if gas_price is None:
            gas_price = self.config['GAS_PRICE']
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

    def get_eligible_proposer(self, shard_id, period=None, gas=TX_GAS):
        """get_eligible_proposer(shard_id: num, period: num) -> address
        """
        if gas is None:
            gas = self.config['DEFAULT_GAS']
        if period is None:
            period = self.web3.eth.blockNumber // PERIOD_LENGTH
        tx_detail = self.mk_contract_tx_detail(sender_address=self.default_sender_address, gas=gas)
        address_in_hex = self.call(tx_detail).get_eligible_proposer(shard_id, period)
        return decode_hex(address_in_hex)

    def deposit(self,
                validation_code_addr,
                return_addr,
                gas=None,
                gas_price=None):
        """deposit(validation_code_addr: address, return_addr: address) -> num
        """
        tx_hash = self.send_transaction(
            'deposit',
            [
                to_checksum_address(validation_code_addr),
                to_checksum_address(return_addr),
            ],
            value=self.config['DEPOSIT_SIZE'],
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def withdraw(self, validator_index, sig, gas=None, gas_price=None):
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

    def add_header(self, header, gas=None, gas_price=None):
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
                    gas=None,
                    gas_price=None):
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
