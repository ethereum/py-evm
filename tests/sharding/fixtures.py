import functools
import pytest

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
    decode_hex,
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

from evm.vm.forks.byzantium.transactions import (
    ByzantiumTransaction,
)

from evm.rlp.headers import (
    CollationHeader,
)

from evm.utils.address import (
    generate_contract_address,
)

from evm.vm.forks.sharding.config import (
    get_sharding_config,
)
from evm.vm.forks.sharding.constants import (
    GENESIS_COLLATION_HASH,
)
from evm.vm.forks.sharding.log_handler import (
    LogHandler,
)
from evm.vm.forks.sharding.shard_tracker import (
    ShardTracker,
)
from evm.vm.forks.sharding.smc_handler import (
    SMCHandler,
    make_call_context,
)
from evm.vm.forks.sharding.smc_utils import (
    get_smc_json,
)
from evm.vm.forks.sharding.windback_worker import (
    WindbackWorker,
)

from tests.sharding.web3_utils import (
    get_code,
    get_nonce,
    send_raw_transaction,
    mine,
)


default_shard_id = 0


def make_deploy_smc_tx(TransactionClass, gas_price):
    smc_json = get_smc_json()
    smc_bytecode = decode_hex(smc_json['bytecode'])
    v = 27
    r = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    s = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    return TransactionClass(0, gas_price, 3000000, b'', 0, smc_bytecode, v, r, s)


def get_contract_address_from_deploy_tx(transaction):
    return pipe(
        transaction.sender,
        to_canonical_address,
        functools.partial(generate_contract_address, nonce=0),
    )


def deploy_smc_contract(web3, gas_price, privkey):
    deploy_smc_tx = make_deploy_smc_tx(ByzantiumTransaction, gas_price=gas_price)

    # fund the smc contract deployer
    fund_deployer_tx = ByzantiumTransaction.create_unsigned_transaction(
        get_nonce(web3, privkey.public_key.to_canonical_address()),
        gas_price,
        500000,
        deploy_smc_tx.sender,
        deploy_smc_tx.gas * deploy_smc_tx.gas_price + deploy_smc_tx.value,
        b'',
    ).as_signed_transaction(privkey)
    fund_deployer_tx_hash = send_raw_transaction(web3, fund_deployer_tx)
    mine(web3, 1)
    assert web3.eth.getTransactionReceipt(fund_deployer_tx_hash) is not None

    # deploy smc contract
    deploy_smc_tx_hash = send_raw_transaction(web3, deploy_smc_tx)
    mine(web3, 1)
    assert web3.eth.getTransactionReceipt(deploy_smc_tx_hash) is not None

    return get_contract_address_from_deploy_tx(deploy_smc_tx)


def add_collator_candidate(smc_handler):
    smc_handler.deposit()
    # TODO: error occurs when we don't mine so many blocks
    lookahead_blocks = (
        smc_handler.config['LOOKAHEAD_PERIODS'] * smc_handler.config['PERIOD_LENGTH']
    )
    mine(smc_handler.web3, lookahead_blocks)


@pytest.fixture
def smc_handler():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    if hasattr(w3.eth, "enable_unaudited_features"):
        w3.eth.enable_unaudited_features()

    default_privkey = get_default_account_keys()[0]
    # deploy smc contract
    smc_addr = deploy_smc_contract(
        w3,
        get_sharding_config()['GAS_PRICE'],
        default_privkey,
    )
    assert get_code(w3, smc_addr) != b''

    # setup smc_handler's web3.eth.contract instance
    smc_json = get_smc_json()
    smc_abi = smc_json['abi']
    smc_bytecode = smc_json['bytecode']
    SMCHandlerClass = SMCHandler.factory(w3, abi=smc_abi, bytecode=smc_bytecode)
    smc_handler = SMCHandlerClass(
        to_checksum_address(smc_addr),
        default_privkey=default_privkey,
    )
    add_collator_candidate(smc_handler)

    return smc_handler


def make_testing_colhdr(smc_handler,  # noqa: F811
                        shard_id,
                        parent_hash,
                        number,
                        coinbase=None):
    if coinbase is None:
        coinbase = smc_handler.sender_address
    period_length = smc_handler.config['PERIOD_LENGTH']
    current_block_number = smc_handler.web3.eth.blockNumber
    expected_period_number = (current_block_number + 1) // period_length

    period_start_prevblock_number = expected_period_number * period_length - 1
    period_start_prev_block = smc_handler.web3.eth.getBlock(period_start_prevblock_number)
    period_start_prevhash = period_start_prev_block['hash']

    transaction_root = b"tx_list " * 4
    state_root = b"post_sta" * 4
    receipt_root = b"receipt " * 4

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


def add_header_constant_call(smc_handler, collation_header):  # noqa: F811
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
    # is the same as the one of parameters of `SMCHandler.add_header`
    result = smc_handler.functions.add_header(*args_with_checksum_address).call(
        make_call_context(
            sender_address=smc_handler.sender_address,
            gas=smc_handler.config['DEFAULT_GAS'],
            gas_price=1,
        )
    )
    return result


def make_collation_header_chain(smc_handler,
                                shard_id,
                                num_collations,
                                top_collation_hash=GENESIS_COLLATION_HASH):
    """
    Make a collation header chain from genesis collation
    :return: the collation hash of the tip of the chain
    """
    for _ in range(num_collations):
        top_collation_number = smc_handler.get_collation_score(shard_id, top_collation_hash)
        header = make_testing_colhdr(
            smc_handler,
            shard_id,
            top_collation_hash,
            top_collation_number + 1,
        )
        assert add_header_constant_call(smc_handler, header)
        tx_hash = smc_handler.add_header(header)
        mine(smc_handler.web3, smc_handler.config['PERIOD_LENGTH'])
        assert smc_handler.web3.eth.getTransactionReceipt(tx_hash) is not None
        top_collation_hash = header.hash
    return top_collation_hash


@pytest.fixture
def shard_tracker(smc_instance, shard_id):
    log_handler = LogHandler(smc_instance.web3)
    return ShardTracker(shard_id, log_handler, smc_instance.address)


@pytest.fixture
def windback_worker(smc_handler):
    return WindbackWorker(
        smc_handler,
        shard_tracker(smc_handler, default_shard_id),
        smc_handler.sender_address,
    )
