import logging

import functools

import pytest

import rlp

from cytoolz import (
    pipe,
)

from web3 import (
    Web3,
)

from web3.providers.eth_tester import (
    EthereumTesterProvider,
)

from eth_utils import (
    is_address,
    to_canonical_address,
    to_checksum_address,
)

from eth_tester import (
    EthereumTester,
)

from eth_tester.backends.pyevm import (
    PyEVMBackend,
)

from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)


from evm.constants import (
    ZERO_ADDRESS,
)


from evm.rlp.headers import (
    CollationHeader,
)
from evm.utils.address import (
    generate_contract_address,
)

from evm.vm.forks.byzantium.transactions import (
    ByzantiumTransaction,
)

from evm.vm.forks.sharding.config import (
    get_sharding_config,
)
from evm.vm.forks.sharding.constants import (
    GENESIS_COLLATION_HASH,
)
from evm.vm.forks.sharding.guess_head_state_manager import (
    GuessHeadStateManager,
)
from evm.vm.forks.sharding.log_handler import (
    LogHandler,
)
from evm.vm.forks.sharding.vmc_handler import (
    ShardTracker,
    VMC,
)
from evm.vm.forks.sharding.vmc_utils import (
    create_vmc_tx,
    get_vmc_json,
)


PASSPHRASE = '123'

logger = logging.getLogger('evm.chain.sharding.mainchain_handler.VMCHandler')

default_shard_id = 0
default_validator_index = 0


def get_contract_address_from_contract_tx(transaction):
    return pipe(
        transaction.sender,
        to_canonical_address,
        functools.partial(generate_contract_address, nonce=0),
    )


def send_deposit_tx(vmc_handler):
    """
    Do deposit in VMC to be a validator

    :param privkey: PrivateKey object
    :return: returns the validator's address
    """
    vmc_handler.deposit()
    mine(vmc_handler, vmc_handler.config['PERIOD_LENGTH'])
    return vmc_handler.get_default_sender_address()


def setup_shard_tracker(vmc_handler, shard_id):
    log_handler = LogHandler(vmc_handler.web3)
    shard_tracker = ShardTracker(shard_id, log_handler, vmc_handler.address)
    vmc_handler.set_shard_tracker(shard_id, shard_tracker)


def send_withdraw_tx(vmc_handler, validator_index):
    assert validator_index < len(get_default_account_keys())
    vmc_handler.withdraw(validator_index)
    mine(vmc_handler, 1)


def get_collation_score_call(vmc_instance, shard_id, collation_hash):
    collation_score = vmc_instance.functions.get_collation_headers__score(
        default_shard_id,
        collation_hash,
    ).call(
        vmc_instance.mk_default_contract_tx_detail(),
    )
    return collation_score


def mk_testing_colhdr(vmc_instance,
                      shard_id,
                      parent_hash,
                      number,
                      coinbase=None):
    period_length = vmc_instance.config['PERIOD_LENGTH']
    current_block_number = vmc_instance.web3.eth.blockNumber
    expected_period_number = current_block_number // period_length
    vmc_instance.logger.debug(
        "mk_testing_colhdr: expected_period_number=%s",
        expected_period_number,
    )

    period_start_prevblock_number = expected_period_number * period_length - 1
    period_start_prev_block = vmc_instance.web3.eth.getBlock(period_start_prevblock_number)
    period_start_prevhash = period_start_prev_block['hash']
    vmc_instance.logger.debug("mk_testing_colhdr: period_start_prevhash=%s", period_start_prevhash)

    transaction_root = b"tx_list " * 4
    state_root = b"post_sta" * 4
    receipt_root = b"receipt " * 4

    if coinbase is None:
        coinbase = vmc_instance.get_default_sender_address()

    collation_header = CollationHeader(
        shard_id=shard_id,
        expected_period_number=expected_period_number,
        period_start_prevhash=period_start_prevhash,
        parent_hash=parent_hash,
        transaction_root=transaction_root,
        coinbase=coinbase,
        state_root=state_root,
        receipt_root=receipt_root,
        number=number,
    )
    return collation_header


def add_header_constant_call(vmc_instance, collation_header):
    args = (
        getattr(collation_header, field[0])
        for field in collation_header.fields
    )
    # transform address from canonical to checksum_address, to comply with web3.py
    args_with_checksum_address = (
        to_checksum_address(item) if is_address(item) else item
        for item in args
    )
    # Here we use *args_with_checksum_address as the argument, to ensure the order of arguments
    # is the same as the one of parameters of `VMC.add_header`
    result = vmc_instance.functions.add_header(
        *args_with_checksum_address
    ).call(
        vmc_instance.mk_default_contract_tx_detail(
            sender_address=vmc_instance.get_default_sender_address(),
            gas=vmc_instance.config['DEFAULT_GAS'],
            gas_price=1,
        )
    )
    return result


def mk_colhdr_chain(vmc_instance,
                    shard_id,
                    num_collations,
                    top_collation_hash=GENESIS_COLLATION_HASH):
    """
    Make a collation header chain from genesis collation
    :return: the collation hash of the tip of the chain
    """
    for _ in range(num_collations):
        top_collation_number = get_collation_score_call(vmc_instance, shard_id, top_collation_hash)
        header = mk_testing_colhdr(
            vmc_instance,
            shard_id,
            top_collation_hash,
            top_collation_number + 1,
        )
        assert add_header_constant_call(vmc_instance, header)
        tx_hash = vmc_instance.add_header(header)
        mine(vmc_instance, vmc_instance.config['PERIOD_LENGTH'])
        assert vmc_instance.web3.eth.getTransactionReceipt(tx_hash) is not None
        top_collation_hash = header.hash
    return top_collation_hash


def mk_initiating_transactions(sender_privkey,
                               sender_starting_nonce,
                               TransactionClass,
                               gas_price):
    """Make VMC and its dependent transactions
    """
    nonce = sender_starting_nonce

    vmc_tx = create_vmc_tx(TransactionClass, gas_price=gas_price)

    # the sender gives all senders of the txs money, and append the
    # money-giving tx with the original tx to the return list

    funding_tx_for_tx_sender = TransactionClass.create_unsigned_transaction(
        nonce,
        gas_price,
        500000,
        vmc_tx.sender,
        vmc_tx.gas * vmc_tx.gas_price + vmc_tx.value,
        b'',
    ).as_signed_transaction(sender_privkey)
    nonce += 1
    return funding_tx_for_tx_sender, vmc_tx


def mine(vmc_handler, num_blocks):
    vmc_handler.web3.testing.mine(num_blocks)


def send_raw_transaction(vmc_handler, raw_transaction):
    w3 = vmc_handler.web3
    raw_transaction_bytes = rlp.encode(raw_transaction)
    raw_transaction_hex = w3.toHex(raw_transaction_bytes)
    transaction_hash = w3.eth.sendRawTransaction(raw_transaction_hex)
    return transaction_hash


def get_nonce(vmc_handler, address):
    return vmc_handler.web3.eth.getTransactionCount(to_checksum_address(address))


def deploy_initiating_contracts(vmc_handler, privkey):
    w3 = vmc_handler.web3
    nonce = get_nonce(vmc_handler, privkey.public_key.to_canonical_address())
    txs = mk_initiating_transactions(
        privkey,
        nonce,
        ByzantiumTransaction,
        vmc_handler.config['GAS_PRICE'],
    )
    for tx in txs:
        tx_hash = send_raw_transaction(vmc_handler, tx)
        mine(vmc_handler, 1)
        assert w3.eth.getTransactionReceipt(tx_hash) is not None


def add_validator(vmc_handler):
    lookahead_blocks = vmc_handler.config['LOOKAHEAD_PERIODS'] * vmc_handler.config['PERIOD_LENGTH']
    # test `deposit` and `get_eligible_proposer` ######################################
    # now we require 1 validator.
    # if there is currently no validator, we deposit one.
    # else, there should only be one validator, for easier testing.
    num_validators = vmc_handler.functions.get_num_validators().call(
        vmc_handler.mk_default_contract_tx_detail(),
    )

    validator_addr = send_deposit_tx(vmc_handler)
    # TODO: error occurs when we don't mine so many blocks
    mine(vmc_handler, lookahead_blocks)
    assert vmc_handler.get_eligible_proposer(default_shard_id) == validator_addr

    # assert the current_block_number >= LOOKAHEAD_PERIODS * PERIOD_LENGTH
    # to ensure that `get_eligible_proposer` works
    current_block_number = vmc_handler.web3.eth.blockNumber
    if current_block_number < lookahead_blocks:
        mine(vmc_handler, lookahead_blocks - current_block_number)
    assert vmc_handler.web3.eth.blockNumber >= lookahead_blocks

    current_num_validators = vmc_handler.functions.get_num_validators().call(
        vmc_handler.mk_default_contract_tx_detail(),
    )
    assert current_num_validators == num_validators + 1
    assert vmc_handler.get_eligible_proposer(default_shard_id) != ZERO_ADDRESS
    vmc_handler.logger.debug("vmc_handler.get_num_validators()=%s", num_validators)


@pytest.fixture
def vmc_handler():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    if hasattr(w3.eth, "enable_unaudited_features"):
        w3.eth.enable_unaudited_features()

    # setup vmc's web3.eth.contract instance
    vmc_tx = create_vmc_tx(
        ByzantiumTransaction,
        get_sharding_config()['GAS_PRICE'],
    )
    vmc_addr = get_contract_address_from_contract_tx(vmc_tx)
    vmc_json = get_vmc_json()
    vmc_abi = vmc_json['abi']
    vmc_bytecode = vmc_json['bytecode']
    VMCClass = VMC.factory(w3, abi=vmc_abi, bytecode=vmc_bytecode)
    vmc_handler = VMCClass(
        to_checksum_address(vmc_addr),
        default_privkey=get_default_account_keys()[0],
    )
    vmc_handler.vmc_tx_sender_address = vmc_tx.sender
    return vmc_handler


@pytest.fixture
def vmc(vmc_handler):
    # test the deployment of vmc ######################################
    deploy_initiating_contracts(vmc_handler, vmc_handler.default_privkey)
    add_validator(vmc_handler)
    mine(vmc_handler, 1)
    return vmc_handler


@pytest.fixture
def ghs_manager(vmc):
    setup_shard_tracker(vmc, default_shard_id)
    ghs_manager = GuessHeadStateManager(
        vmc,
        default_shard_id,
        vmc.get_default_sender_address(),
    )
    return ghs_manager
