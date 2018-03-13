import logging
from typing import (  # noqa: F401
    Dict
)

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

from evm.vm.forks.sharding.config import (
    get_sharding_config,
)


@to_dict
def mk_contract_tx_detail(sender_address,
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


@to_dict
def mk_build_transaction_detail(nonce,
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


class VMC(Contract):

    logger = logging.getLogger("evm.chain.sharding.VMC")

    def __init__(self, *args, default_privkey, **kwargs):
        self.default_privkey = default_privkey
        self.default_sender_address = default_privkey.public_key.to_canonical_address()
        self.config = get_sharding_config()
        self.shard_trackers = {}  # type: Dict[int, ShardTracker]

        super().__init__(*args, **kwargs)

    def get_default_sender_address(self):
        return self.default_sender_address

    def mk_default_contract_tx_detail(self,
                                      sender_address=None,
                                      gas=None,
                                      value=None,
                                      gas_price=None,
                                      data=None):
        if sender_address is None:
            sender_address = self.default_sender_address
        if gas is None:
            gas = self.config['DEFAULT_GAS']
        default_contract_tx_detail = mk_contract_tx_detail(
            sender_address,
            gas,
            value,
            gas_price,
            data,
        )
        return default_contract_tx_detail

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
        build_transaction_detail = mk_build_transaction_detail(
            nonce=nonce,
            gas=gas,
            chain_id=chain_id,
            value=value,
            gas_price=gas_price,
            data=data,
        )
        func_instance = getattr(self.functions, func_name)
        unsigned_transaction = func_instance(*args).buildTransaction(
            transaction=build_transaction_detail,
        )
        signed_transaction_dict = self.web3.eth.account.signTransaction(
            unsigned_transaction,
            privkey.to_hex(),
        )
        tx_hash = self.web3.eth.sendRawTransaction(signed_transaction_dict['rawTransaction'])
        return tx_hash

    # contract calls ##############################################

    def get_eligible_proposer(self, shard_id, period=None, gas=None):
        """Get the eligible proposer in the specified period
        """
        if period is None:
            period = self.web3.eth.blockNumber // self.config['PERIOD_LENGTH']
        tx_detail = self.mk_default_contract_tx_detail(gas=gas)
        address_in_hex = self.functions.get_eligible_proposer(shard_id, period).call(tx_detail)
        return decode_hex(address_in_hex)

    def get_parent_hash(self, shard_id, collation_hash, gas=None):
        if gas is None:
            gas = self.config['DEFAULT_GAS']
        tx_detail = self.mk_default_contract_tx_detail(gas=gas)
        return self.functions.get_collation_headers__parent_hash(
            shard_id,
            collation_hash,
        ).call(tx_detail)

    def deposit(self, gas=None, gas_price=None):
        """Do deposit to become a validator
        """
        tx_hash = self.send_transaction(
            'deposit',
            [],
            value=self.config['DEPOSIT_SIZE'],
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def withdraw(self, validator_index, gas=None, gas_price=None):
        """Withdraw the validator whose index is `validator_index`
        """
        tx_hash = self.send_transaction(
            'withdraw',
            [
                validator_index,
            ],
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def add_header(self,
                   collation_header,
                   gas=None,
                   gas_price=None):
        """Add the collation header with the given parameters
        """
        tx_hash = self.send_transaction(
            'add_header',
            [
                collation_header.shard_id,
                collation_header.expected_period_number,
                collation_header.period_start_prevhash,
                collation_header.parent_hash,
                collation_header.transaction_root,
                to_checksum_address(collation_header.coinbase),
                collation_header.state_root,
                collation_header.receipt_root,
                collation_header.number,
            ],
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
        """Make a receipt with the given parameters
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
