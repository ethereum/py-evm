from evm.constants import (
    ENTRY_POINT,
)

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
from evm.utils.keccak import (
    keccak,
)
from evm.vm.forks.byzantium.vm_state import ByzantiumVMState
from evm.vm.forks.frontier.constants import (
    REFUND_SELFDESTRUCT,
)

from .blocks import ShardingBlock
from .computation import ShardingComputation
from .validation import validate_sharding_transaction


class ShardingVMState(ByzantiumVMState):
    block_class = ShardingBlock
    computation_class = ShardingComputation

    def execute_transaction(self, transaction):
        #
        # 1) Pre Computation
        #

        # Validate the transaction
        transaction.validate()

        self.validate_transaction(transaction)

        gas_fee = transaction.gas * transaction.gas_price
        with self.state_db() as state_db:
            # Buy Gas
            state_db.delta_balance(transaction.to, -1 * gas_fee)

            # Setup VM Message
            message_gas = transaction.gas - transaction.intrinsic_gas

            if transaction.code:
                contract_address = generate_CREATE2_contract_address(
                    b'',
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
                "gas-price: %s | data-hash: %s | code-hash: %s"
            ),
            encode_hex(transaction.to),
            transaction.gas,
            transaction.gas_price,
            encode_hex(keccak(transaction.data)),
            encode_hex(keccak(transaction.code)),
        )

        message = ShardingMessage(
            gas=message_gas,
            gas_price=transaction.gas_price,
            to=transaction.to,
            sig_hash=transaction.sig_hash,
            sender=ENTRY_POINT,
            value=0,
            data=data,
            code=code,
            is_create=is_create,
        )

        #
        # 2) Apply the message to the VM.
        #
        if message.is_create:
            with self.state_db(read_only=True) as state_db:
                is_collision = state_db.account_has_code_or_nonce(contract_address)

            # Check if contract address provided by transaction is correct
            if contract_address != transaction.to:
                computation = self.get_computation(message)
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
                computation = self.get_computation(message)
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
                computation = self.get_computation(message).apply_create_message()
        else:
            computation = self.get_computation(message).apply_message()

        #
        # 2) Post Computation
        #
        # Self Destruct Refunds
        num_deletions = len(computation.get_accounts_for_deletion())
        if num_deletions:
            computation.gas_meter.refund_gas(REFUND_SELFDESTRUCT * num_deletions)

        # Gas Refunds
        gas_remaining = computation.get_gas_remaining()
        gas_refunded = computation.get_gas_refund()
        gas_used = transaction.gas - gas_remaining
        gas_refund = min(gas_refunded, gas_used // 2)
        gas_refund_amount = (gas_refund + gas_remaining) * transaction.gas_price

        if gas_refund_amount:
            self.logger.debug(
                'TRANSACTION REFUND: %s -> %s',
                gas_refund_amount,
                encode_hex(message.to),
            )

            with self.state_db() as state_db:
                state_db.delta_balance(message.to, gas_refund_amount)

        # Miner Fees
        transaction_fee = (transaction.gas - gas_remaining - gas_refund) * transaction.gas_price
        self.logger.debug(
            'TRANSACTION FEE: %s -> %s',
            transaction_fee,
            encode_hex(self.coinbase),
        )
        with self.state_db() as state_db:
            state_db.delta_balance(self.coinbase, transaction_fee)

        # Process Self Destructs
        with self.state_db() as state_db:
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
