import functools
from cytoolz import (
    merge,
)

from eth_utils import (
    keccak,
)
from trie import (
    BinaryTrie,
)

from evm.constants import (
    ENTRY_POINT,
)

from evm.db.trie import make_trie_root_and_nodes

from evm.exceptions import (
    ContractCreationCollision,
    IncorrectContractCreationAddress,
)

from evm.vm.message import (
    ShardingMessage,
)
from evm.utils.address import (
    generate_CREATE2_contract_address,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.vm.forks.byzantium.vm_state import ByzantiumVMState
from evm.vm.forks.frontier.constants import (
    REFUND_SELFDESTRUCT,
)

from .collations import Collation
from .computation import ShardingComputation
from .transaction_context import ShardingTransactionContext
from .validation import validate_sharding_transaction


class ShardingVMState(ByzantiumVMState):
    block_class = Collation
    computation_class = ShardingComputation
    transaction_context_class = ShardingTransactionContext
    trie_class = BinaryTrie

    def execute_transaction(self, transaction):
        # state_db ontext manager that restricts access as specified in the transacion
        state_db_cm = functools.partial(self.state_db, access_list=transaction.prefix_list)

        #
        # 1) Pre Computation
        #

        # Validate the transaction
        transaction.validate()

        self.validate_transaction(transaction)

        with state_db_cm() as state_db:
            # Setup VM Message
            message_gas = transaction.gas - transaction.intrinsic_gas

            if transaction.code:
                contract_address = generate_CREATE2_contract_address(
                    transaction.salt,
                    transaction.code,
                )
                data = b''
                code = transaction.code
                is_create = True
            else:
                contract_address = None
                data = transaction.data
                code = state_db.get_code(transaction.to)
                is_create = False

        self.logger.info(
            (
                "TRANSACTION: to: %s | gas: %s | "
                "data-hash: %s | code-hash: %s | salt: %s"
            ),
            encode_hex(transaction.to),
            transaction.gas,
            encode_hex(keccak(transaction.data)),
            encode_hex(keccak(transaction.code)),
            encode_hex(transaction.salt),
        )

        message = ShardingMessage(
            gas=message_gas,
            to=transaction.to,
            sender=ENTRY_POINT,
            value=0,
            data=data,
            code=code,
            is_create=is_create,
            access_list=transaction.prefix_list,
        )
        transaction_context = self.get_transaction_context_class()(
            origin=transaction.to,
            sig_hash=transaction.sig_hash,
            transaction_gas_limit=transaction.gas,
        )

        #
        # 2) Apply the message to the VM.
        #
        if message.is_create:
            with state_db_cm(read_only=True) as state_db:
                is_collision = state_db.account_has_code(contract_address)

            # Check if contract address provided by transaction is correct
            if contract_address != transaction.to:
                computation = self.get_computation(message, transaction_context)
                computation._error = IncorrectContractCreationAddress(
                    "Contract address calculated: {0} but {1} is provided".format(
                        encode_hex(contract_address),
                        encode_hex(transaction.to),
                    )
                )
                self.logger.debug(
                    "Contract address calculated: %s but %s is provided",
                    encode_hex(contract_address),
                    encode_hex(transaction.to),
                )
            elif is_collision:
                # The address of the newly created contract has collided
                # with an existing contract address.
                computation = self.get_computation(message, transaction_context)
                computation._error = ContractCreationCollision(
                    "Address collision while creating contract: {0}".format(
                        encode_hex(contract_address),
                    )
                )
                self.logger.debug(
                    "Address collision while creating contract: %s",
                    encode_hex(contract_address),
                )
            else:
                computation = self.get_computation(
                    message,
                    transaction_context,
                ).apply_create_message()
        else:
            computation = self.get_computation(message, transaction_context).apply_message()

        #
        # 2) Post Computation
        #
        # Self Destruct Refunds
        num_deletions = len(computation.get_accounts_for_deletion())
        if num_deletions:
            computation.gas_meter.refund_gas(REFUND_SELFDESTRUCT * num_deletions)

        # Gas Refunds
        transaction_fee, gas_refund_amount = computation.compute_transaction_fee_and_refund()

        if gas_refund_amount:
            self.logger.debug(
                'TRANSACTION REFUND: %s -> %s',
                gas_refund_amount,
                encode_hex(message.to),
            )

            with state_db_cm() as state_db:
                state_db.delta_balance(message.to, gas_refund_amount)

        # Miner Fees
        self.logger.debug(
            'TRANSACTION FEE: %s',
            transaction_fee,
        )

        # Process Self Destructs
        with state_db_cm() as state_db:
            for account, beneficiary in computation.get_accounts_for_deletion():
                # TODO: need to figure out how we prevent multiple selfdestructs from
                # the same account and if this is the right place to put this.
                self.logger.debug('DELETING ACCOUNT: %s', encode_hex(account))

                # TODO: this balance setting is likely superflous and can be
                # removed since `delete_account` does this.
                state_db.set_balance(account, 0)
                state_db.delete_account(account)

        return computation

    def validate_transaction(self, transaction):
        validate_sharding_transaction(self, transaction)

    def add_transaction(self, transaction, computation, block):
        """
        Add a transaction to the given block and
        return `trie_data` to store the transaction data in chaindb in VM layer.

        Update the bloom_filter, transaction trie and receipt trie roots, bloom_filter,
        bloom, and used_gas of the block.

        :param transaction: the executed transaction
        :param computation: the Computation object with executed result
        :param block: the Block which the transaction is added in
        :type transaction: Transaction
        :type computation: Computation
        :type block: Block

        :return: the block and the trie_data
        :rtype: (Block, dict[bytes, bytes])
        """
        receipt = self.make_receipt(transaction, computation)
        self.add_receipt(receipt)

        # Create a new Block object
        block_header = block.header.clone()
        transactions = list(block.transactions)
        block = self.block_class(block_header, transactions)

        block.transactions.append(transaction)

        # Calculate transaction fee
        transaction_fee, _ = computation.compute_transaction_fee_and_refund()
        # Bookkeep this transaction fee
        block.transaction_fee_sum += transaction_fee

        # Get trie roots and changed key-values.
        tx_root_hash, tx_kv_nodes = make_trie_root_and_nodes(block.transactions)
        receipt_root_hash, receipt_kv_nodes = make_trie_root_and_nodes(
            self.receipts,
            trie_class=BinaryTrie,
        )

        trie_data = merge(tx_kv_nodes, receipt_kv_nodes)

        block.header.transaction_root = tx_root_hash
        block.header.receipt_root = receipt_root_hash
        block.header.gas_used = receipt.gas_used

        return block, trie_data

    def finalize_block(self, block):
        """
        Apply rewards.
        """
        block_reward = self.get_block_reward() + (
            len(block.uncles) * self.get_nephew_reward()
        )

        with self.state_db() as state_db:
            state_db.delta_balance(block.header.coinbase, block.transaction_fee_sum)
            self.logger.debug(
                "TOTAL TRANSACTON FEE: %s -> %s",
                block.transaction_fee_sum,
                block.header.coinbase,
            )

            state_db.delta_balance(block.header.coinbase, block_reward)
            self.logger.debug(
                "BLOCK REWARD: %s -> %s",
                block_reward,
                block.header.coinbase,
            )

        block.header.state_root = self.state_root
        return block
