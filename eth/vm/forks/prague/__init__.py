from hashlib import sha256
from typing import (
    Type,
)

from eth._utils.db import (
    get_block_header_by_hash,
)
from eth.abc import (
    BlockAPI,
)
from eth.constants import (
    SYSTEM_ADDRESS,
    SYSTEM_MESSAGE_GAS,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.vm.forks.cancun import (
    CancunVM,
    get_total_blob_gas,
)
from eth.vm.forks.prague.constants import (
    CONSOLIDATION_REQUEST_PREDEPLOY_ADDRESS,
    CONSOLIDATION_REQUEST_TYPE,
    DEPOSIT_CONTRACT_ADDRESS,
    DEPOSIT_EVENT_SIGNATURE_HASH,
    DEPOSIT_REQUEST_TYPE,
    HISTORY_SERVE_WINDOW,
    HISTORY_STORAGE_ADDRESS,
    HISTORY_STORAGE_CONTRACT_CODE,
    MAX_BLOB_GAS_PER_BLOCK,
    WITHDRAWAL_REQUEST_PREDEPLOY_ADDRESS,
    WITHDRAWAL_REQUEST_TYPE,
)
from eth.vm.state import (
    BaseState,
)
from eth_utils import (
    ValidationError,
    to_bytes,
)

from .blocks import (
    PragueBlock,
)
from .headers import (
    calc_excess_blob_gas_prague,
    create_prague_header_from_parent,
)
from .state import (
    PragueState,
)


class PragueVM(CancunVM):
    # fork name
    fork = "prague"

    # classes
    block_class: Type[BaseBlock] = PragueBlock
    _state_class: Type[BaseState] = PragueState

    # methods
    create_header_from_parent = staticmethod(  # type: ignore
        create_prague_header_from_parent()
    )

    def block_preprocessing(self, block: BlockAPI) -> None:
        super().block_preprocessing(block)

        if (
            self.state.get_code(HISTORY_STORAGE_ADDRESS)
            == HISTORY_STORAGE_CONTRACT_CODE
        ):
            # if the history storage contract exists, update the with the parent hash
            self.state.set_storage(
                HISTORY_STORAGE_ADDRESS,
                (block.number - 1) % HISTORY_SERVE_WINDOW,
                int.from_bytes(block.header.parent_hash, "big"),
            )

    def process_deposit_request_data(self, block: BlockAPI) -> None:
        deposit_request_data = b""
        for receipt in block.get_receipts(self.chaindb):
            for log in receipt.logs:
                is_deposit_event = (
                    len(log.topics) > 0
                    and to_bytes(log.topics[0]) == DEPOSIT_EVENT_SIGNATURE_HASH
                )
                if log.address == DEPOSIT_CONTRACT_ADDRESS and is_deposit_event:
                    deposit_request = (
                        log.data[192:240]  # public_key
                        + log.data[288:320]  # withdrawal_credentials
                        + log.data[352:360]  # amount
                        + log.data[416:512]  # signature
                        + log.data[544:552]  # index
                    )
                    deposit_request_data += deposit_request

        block.block_requests.append(DEPOSIT_REQUEST_TYPE + deposit_request_data)

    def process_withdrawal_request_data(self, block: BlockAPI) -> None:
        if not self.state.get_code(WITHDRAWAL_REQUEST_PREDEPLOY_ADDRESS):
            return

        withdrawal_request_contract_code = self.state.get_code(
            WITHDRAWAL_REQUEST_PREDEPLOY_ADDRESS
        )
        withdrawal_computation = self.execute_bytecode(
            origin=SYSTEM_ADDRESS,
            gas_price=0,
            gas=SYSTEM_MESSAGE_GAS,
            to=WITHDRAWAL_REQUEST_PREDEPLOY_ADDRESS,
            sender=SYSTEM_ADDRESS,
            value=0,
            data=b"",
            code=withdrawal_request_contract_code,
            code_address=WITHDRAWAL_REQUEST_PREDEPLOY_ADDRESS,
        )

        if len(withdrawal_computation.output) > 0:
            block.block_requests.append(
                WITHDRAWAL_REQUEST_TYPE + withdrawal_computation.output
            )

    def process_consolidation_request_data(self, block: BlockAPI) -> None:
        if not self.state.get_code(CONSOLIDATION_REQUEST_PREDEPLOY_ADDRESS):
            return

        consolidation_request_contract_code = self.state.get_code(
            CONSOLIDATION_REQUEST_PREDEPLOY_ADDRESS
        )
        consolidation_computation = self.execute_bytecode(
            origin=SYSTEM_ADDRESS,
            gas_price=0,
            gas=SYSTEM_MESSAGE_GAS,
            to=CONSOLIDATION_REQUEST_PREDEPLOY_ADDRESS,
            sender=SYSTEM_ADDRESS,
            value=0,
            data=b"",
            code=consolidation_request_contract_code,
            code_address=CONSOLIDATION_REQUEST_PREDEPLOY_ADDRESS,
        )

        if len(consolidation_computation.output) > 0:
            block.block_requests.append(
                CONSOLIDATION_REQUEST_TYPE + consolidation_computation.output
            )

    @staticmethod
    def compute_requests_hash(block: BlockAPI) -> BlockAPI:
        m = sha256()
        for r in block.block_requests:
            if len(r) > 1:
                m.update(sha256(r).digest())

        updated_header = block.header.copy(requests_hash=m.digest())
        return block.copy(header=updated_header)

    def block_postprocessing(self, block: BlockAPI) -> BlockAPI:
        self.process_deposit_request_data(block)  # type 0 block requests
        self.process_withdrawal_request_data(block)  # type 1 block requests
        self.process_consolidation_request_data(block)  # type 2 block requests
        processed_block = self.compute_requests_hash(block)
        return processed_block

    def validate_block_blobs(self, block: BlockAPI) -> None:
        # check that the excess blob gas was updated correctly
        parent_header = get_block_header_by_hash(block.header.parent_hash, self.chaindb)
        if block.header.excess_blob_gas != calc_excess_blob_gas_prague(parent_header):
            raise ValidationError("Block excess blob gas was not updated correctly.")

        blob_gas_used = sum(get_total_blob_gas(tx) for tx in block.transactions)

        # ensure the total blob gas spent is at most equal to the limit
        if blob_gas_used > MAX_BLOB_GAS_PER_BLOCK:
            raise ValidationError("Block exceeded maximum blob gas limit.")

        # ensure blob_gas_used matches header
        block_blob_gas_used = block.header.blob_gas_used
        if block_blob_gas_used != blob_gas_used:
            raise ValidationError(
                f"Block blob gas used ({block_blob_gas_used}) does not match "
                f"total blob gas used ({blob_gas_used})."
            )
