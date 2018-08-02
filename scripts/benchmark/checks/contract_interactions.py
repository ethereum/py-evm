import json
import logging
import pathlib
import re
from typing import (
    Tuple,
    Callable,
    Any,
)

from web3 import (
    Web3,
    utils as w3_utils,
)

from eth_utils import (
    encode_hex,
    decode_hex,
    to_int,
)

from eth.constants import (
    CREATE_CONTRACT_ADDRESS
)
from eth.chains.base import (
    MiningChain,
)
from eth.consensus.pow import (
    mine_pow_nonce
)
from eth.exceptions import (
    InvalidInstruction,
    Revert,
    ValidationError,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.rlp.transactions import (
    BaseTransaction
)
from eth_typing import (
    Address
)
from .base_benchmark import (
    BaseBenchmark,
)
from utils.address import (
    FIRST_ACCOUNT,
    SECOND_ACCOUNT,
)
from utils.chain_plumbing import (
    DB,
    get_all_chains,
)
from utils.compile import (
    get_compiled_contract
)
from utils.reporting import (
    DefaultStat,
)
from utils.tx import (
    new_transaction,
)

w3 = Web3()
W3_TX_DEFAULTS = {'gas': 0, 'gasPrice': 0}

########################
# ERC20 globals
########################
ERC20_CONTRACT_FILE = 'scripts/benchmark/contract_data/erc20.sol'
ERC20_CONTRACT_NAME = 'SimpleToken'

ERC20_contract_interface = get_compiled_contract(
            pathlib.Path(ERC20_CONTRACT_FILE),
            ERC20_CONTRACT_NAME)

ERC20_deployed_contract_address: Address
ERC20_deployed_contract: Address

ERC_TRANSFER_AMOUNT = 1000
ERC_TRANSER_FROM_AMOUNT = 1

########################
# DOS globals
########################
DOS_CONTRACT_FILE = 'scripts/benchmark/contract_data/DOSContract.sol'
DOS_CONTRACT_NAME = 'DOSContract'

DOS_contract_interface = get_compiled_contract(
            pathlib.Path(DOS_CONTRACT_FILE),
            DOS_CONTRACT_NAME)

DOS_deployed_contract_address: Address
DOS_deployed_contract: Address

########################
# Create ERC20 Transactions
########################
def deploy_erc20(chain: MiningChain, gas: int=1400000) -> BaseTransaction:
    # tx computation should succeed
    computation_success = True
    # Instantiate the contract
    SimpleToken = w3.eth.contract(
        abi=ERC20_contract_interface['abi'],
        bytecode=ERC20_contract_interface['bin']
    )
    # Build transaction to deploy the contract
    # build tx data using Web3
    w3_tx = SimpleToken.constructor().buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FIRST_ACCOUNT.private_key,
        from_=FIRST_ACCOUNT.address,
        to=CREATE_CONTRACT_ADDRESS,
        amount=0,
        gas=gas,
        data=decode_hex(w3_tx['data']),
    )
    return tx, computation_success


def transfer_erc20(chain: MiningChain, gas: int=1400000) -> BaseTransaction:
    # tx computation should succeed
    computation_success = True
    # build tx data using Web3
    w3_tx = ERC20_deployed_contract.functions.transfer(
        SECOND_ACCOUNT.checksum_address,
        ERC_TRANSFER_AMOUNT
    ).buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FIRST_ACCOUNT.private_key,
        from_=FIRST_ACCOUNT.address,
        to=ERC20_deployed_contract_address,
        amount=0,
        gas=gas,
        data=decode_hex(w3_tx['data']),
    )
    return tx, computation_success


def approve_erc20(chain: MiningChain, gas: int=1400000) -> BaseTransaction:
    # tx computation should succeed
    computation_success = True
    # build tx data using Web3
    w3_tx = ERC20_deployed_contract.functions.approve(
        SECOND_ACCOUNT.checksum_address,
        ERC_TRANSFER_AMOUNT
    ).buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FIRST_ACCOUNT.private_key,
        from_=FIRST_ACCOUNT.address,
        to=ERC20_deployed_contract_address,
        amount=0,
        gas=gas,
        data=decode_hex(w3_tx['data']),
    )
    return tx, computation_success


def transfer_from_erc20(chain: MiningChain, gas: int=1400000) -> BaseTransaction:
    # tx computation should succeed
    computation_success = True
    # requires approve to be called in order to execute successfully
    # build tx data using Web3
    w3_tx = ERC20_deployed_contract.functions.transferFrom(
        FIRST_ACCOUNT.checksum_address,
        SECOND_ACCOUNT.checksum_address,
        ERC_TRANSER_FROM_AMOUNT
    ).buildTransaction(W3_TX_DEFAULTS)
    # create transaction
    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=SECOND_ACCOUNT.private_key,
        from_=SECOND_ACCOUNT.address,
        to=ERC20_deployed_contract_address,
        amount=0,
        gas=gas,
        data=decode_hex(w3_tx['data']),
    )
    return tx, computation_success

########################
# ERC20 SETUP
########################
def deployed_erc20_contract(chain: MiningChain):
    global ERC20_deployed_contract_address
    global ERC20_deployed_contract
    tx, computation_success = deploy_erc20(chain)
    tx_gas_est = chain.estimate_gas(tx)
    tx, computation_success = deploy_erc20(chain, tx_gas_est)
    block, receipt, computation = chain.apply_transaction(tx)
    if (computation_success):
        computation.is_success

    # get contract to interact with
    logging.debug('Applying Transaction {}'.format(tx))
    # apply transaction to block
    # Keep track of deployed contract address
    ERC20_deployed_contract_address = computation.msg.storage_address
    assert computation.is_success
    # Keep track of simple_token object for further interaction
    ERC20_deployed_contract = w3.eth.contract(
        address=Web3.toChecksumAddress(encode_hex(ERC20_deployed_contract_address)),
        abi=ERC20_contract_interface['abi'],
    )

def approved_erc20(chain: MiningChain):
    tx, computation_success = approve_erc20(chain)
    tx_gas_est = chain.estimate_gas(tx)
    tx, computation_success = approve_erc20(chain, tx_gas_est)
    block, receipt, computation = chain.apply_transaction(tx)
    if (computation_success):
        computation.is_success


########################
# Create Denial of Service (DOS) Transactions
########################
def deploy_dos(chain: MiningChain, gas: int=1400000) -> BaseTransaction:
    # tx computation should succeed
    computation_success = True
    # Instantiate the contract
    DOS_deployed_contract = w3.eth.contract(
        abi=DOS_contract_interface['abi'],
        bytecode=DOS_contract_interface['bin']
    )

    # Build transaction to deploy the contract
    w3_tx = DOS_deployed_contract.constructor().buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FIRST_ACCOUNT.private_key,
        from_=FIRST_ACCOUNT.address,
        to=CREATE_CONTRACT_ADDRESS,
        amount=0,
        gas=gas,
        data=decode_hex(w3_tx['data']),
    )
    return tx, computation_success


def sstore_uint64_dos(chain: MiningChain, gas: int=1400000) -> BaseTransaction:
    # tx computation should succeed
    computation_success = True
    # build tx data using Web3
    w3_tx = DOS_deployed_contract.functions.storageEntropy().buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FIRST_ACCOUNT.private_key,
        from_=FIRST_ACCOUNT.address,
        to=DOS_deployed_contract_address,
        amount=0,
        gas=gas,
        data=decode_hex(w3_tx['data']),
    )
    return tx, computation_success


def create_empty_contract_dos(chain: MiningChain, gas: int=1400000) -> BaseTransaction:
    # tx computation should succeed
    computation_success = True
    # build tx data using Web3
    w3_tx = DOS_deployed_contract.functions.createEmptyContract().buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FIRST_ACCOUNT.private_key,
        from_=FIRST_ACCOUNT.address,
        to=DOS_deployed_contract_address,
        amount=0,
        gas=gas,
        data=decode_hex(w3_tx['data']),
    )
    return tx, computation_success


def sstore_uint64_revert_dos(chain: MiningChain, gas: int=21272) -> BaseTransaction:
    # tx computation should NOT succeed
    computation_success = False
    # build tx data using Web3
    w3_tx = DOS_deployed_contract.functions.storageEntropyRevert().buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FIRST_ACCOUNT.private_key,
        from_=FIRST_ACCOUNT.address,
        to=DOS_deployed_contract_address,
        amount=0,
        gas=gas,
        data=decode_hex(w3_tx['data']),
    )
    return tx, computation_success


def create_empty_contract_revert_dos(chain: MiningChain, gas: int=21273) -> BaseTransaction:
    # tx computation should NOT succeed
    computation_success = False
    # build tx data using Web3
    w3_tx = DOS_deployed_contract.functions.createEmptyContractRevert().buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FIRST_ACCOUNT.private_key,
        from_=FIRST_ACCOUNT.address,
        to=DOS_deployed_contract_address,
        amount=0,
        gas=gas,
        data=decode_hex(w3_tx['data']),
    )
    return tx, computation_success

########################
# DOS SETUP
########################
def deployed_dos_contract(chain: MiningChain):
    global DOS_deployed_contract_address
    global DOS_deployed_contract
    tx, computation_success = deploy_dos(chain)
    tx_gas_est = chain.estimate_gas(tx)
    tx, computation_success = deploy_dos(chain, tx_gas_est)
    block, receipt, computation = chain.apply_transaction(tx)
    if (computation_success):
        computation.is_success

    # get contract to interact with
    logging.debug('Applying Transaction {}'.format(tx))
    # apply transaction to block
    # Keep track of deployed contract address
    DOS_deployed_contract_address = computation.msg.storage_address
    # Keep track of simple_token object for further interaction
    DOS_deployed_contract = w3.eth.contract(
        address=Web3.toChecksumAddress(encode_hex(DOS_deployed_contract_address)),
        abi=DOS_contract_interface['abi'],
    )


class ContractInteractions(BaseBenchmark):
    def __init__(self,
                 benchmark: Callable,
                 setup: Tuple[Callable, ...],
                 db: DB,
                 num_blocks: int,
                 num_tx: int,
                 validate_POW: bool,
                 make_POW_fixture: bool) -> None:

        self.benchmark = benchmark
        self.setup = setup
        self.db = db
        self.num_blocks = num_blocks
        self.num_tx = num_tx
        self.validate_POW = validate_POW
        self.make_POW_fixture = make_POW_fixture
        self.POW_file_path = "scripts/benchmark/fixtures/ContractInteractions/"+ self.name.replace(" ", "_") +".json"
        self.POW_fixture = {}

    @property
    def name(self) -> str:
        return re.search(r'\s(\w+)\s',
                              str(self.benchmark)
                              ).group(1).replace('_', ' ') + " contract benchmark"

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()

        # make the Proof of Work fixture
        if self.make_POW_fixture:
            self.make_POW_fixtures(self.num_blocks, self.num_tx)
            logging.info("CREATED FIXTURE NOT REPORTING STATS")
            total_stat = DefaultStat(total_seconds=1)
            return total_stat

        #####  SETUP  #####
        # load fixtures
        with open(self.POW_file_path, 'r') as outfile:
            self.POW_fixture = json.load(outfile)

        for chain in get_all_chains(self.db, self.validate_POW):
            # Perform prepartions on the chain that do not count into the benchmark time
            if all(self.setup):
                for i, setup in enumerate(self.setup):
                    setup(chain)
                    fixture = self.POW_fixture[chain.get_vm().fork][str(i)]
                    nonce = bytes.fromhex(fixture["nonce"])
                    mix_hash = bytes.fromhex(fixture["mix_hash"])
                    block = chain.mine_block(nonce=nonce, mix_hash=mix_hash)

            block_num = chain.get_block().number
            self.benchmark_gas = self.calculate_min_gas(chain)
            fixture = self.POW_fixture[chain.get_vm().fork][str(block_num)]
            nonce = bytes.fromhex(fixture["nonce"])
            mix_hash = bytes.fromhex(fixture["mix_hash"])
            block = chain.mine_block(nonce=nonce, mix_hash=mix_hash)

            # Perform the actual work that is measured
            value = self.as_timed_result(
                lambda: self.mine_blocks(chain, self.num_blocks, self.num_tx)
            )
            total_gas_used, total_num_tx = value.wrapped_value
            stat = DefaultStat(
                caption=chain.get_vm().fork,
                total_blocks=self.num_blocks,
                total_tx=total_num_tx,
                total_seconds=value.duration,
                total_gas=total_gas_used,
            )
            total_stat = total_stat.cumulate(stat)
            self.print_stat_line(stat)
        return total_stat

    def mine_blocks(self,
                    chain: MiningChain,
                    num_blocks: int,
                    num_tx: int) -> Tuple[int, int]:

        total_gas_used = 0
        total_num_tx = 0
        start_block = chain.get_block().number
        for i in range(start_block, num_blocks + start_block):
            self.mine_block(chain, i, num_tx)
            fixture = self.POW_fixture[chain.get_vm().fork][str(i)]
            nonce = bytes.fromhex(fixture["nonce"])
            mix_hash = bytes.fromhex(fixture["mix_hash"])
            block = chain.mine_block(nonce=nonce, mix_hash=mix_hash)
            total_gas_used = total_gas_used + block.header.gas_used
            total_num_tx = total_num_tx + len(block.transactions)
        return total_gas_used, total_num_tx

    def mine_block(self,
                   chain: MiningChain,
                   block_number: int,
                   num_tx: int):

        for _ in range(1, num_tx + 1):
            tx, computation_success = self.benchmark(chain, self.benchmark_gas)
            block, receipt, computation = chain.apply_transaction(tx)
            if (computation_success):
                computation.is_success

    def make_POW_fixtures (self, num_blocks, num_tx):
        for chain in get_all_chains(self.db, self.validate_POW):
            POW_fork = {}

            if all(self.setup):
                for i, setup in enumerate(self.setup):
                    setup(chain)
                    POW_fork[i] = self.make_POW_block(chain)

            self.benchmark_gas = self.calculate_min_gas(chain)
            block_num = chain.get_block().number
            POW_fork[block_num] = self.make_POW_block(chain)

            start_block = chain.get_block().number
            for i in range(start_block, num_blocks + start_block):
                self.mine_block(chain, num_blocks, num_tx)
                POW_fork[i] = self.make_POW_block(chain)
            self.POW_fixture[chain.get_vm().fork] = POW_fork

        with open(self.POW_file_path, 'w') as outfile:
            json.dump(self.POW_fixture, outfile, indent=4)

    def make_POW_block(self, chain: MiningChain) -> dict:
        POW_block = {}
        block = chain.get_vm().finalize_block(chain.get_block())
        nonce, mix_hash = mine_pow_nonce(
                block.number,
                block.header.mining_hash,
                block.header.difficulty)
        block = chain.mine_block(nonce=nonce, mix_hash=mix_hash)
        POW_block["mix_hash"] = mix_hash.hex()
        POW_block["nonce"] = nonce.hex()
        return POW_block

    def calculate_min_gas(self, chain: MiningChain) -> int:
        min_gas : int
        tx, _ = self.benchmark(chain)
        # try estimate_gas to get min_gas
        try:
             min_gas = chain.estimate_gas(tx)
        except (InvalidInstruction, Revert):
            # apply transactions with decreasing gas to find lower limit
            block, receipt, computation = chain.apply_transaction(tx)
            min_gas = receipt.gas_used
            while True:
                try:
                    tx, _ = self.benchmark(chain, min_gas-1)
                    block, receipt, computation = chain.apply_transaction(tx)
                    min_gas = min_gas-1
                except ValidationError:
                    break
        return min_gas
