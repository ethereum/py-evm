from eth_bloom import (
    BloomFilter,
)
import pytest

from eth.abc import (
    ReceiptBuilderAPI,
    TransactionBuilderAPI,
)
from eth.chains.mainnet import (
    MAINNET_VMS,
)
from eth.rlp.headers import (
    BlockHeader,
)


@pytest.fixture(scope="module")
def genesis_header():
    return BlockHeader(
        difficulty=0,
        block_number=0,
        gas_limit=10000,
    )


@pytest.mark.parametrize("vm_class", MAINNET_VMS)
def test_vm_block_class_is_properly_configured(
    vm_class,
    genesis_header,
):
    vm_block_instance = vm_class.get_block_class()(genesis_header)

    txn_builder = vm_block_instance.get_transaction_builder()
    assert txn_builder is not None
    assert issubclass(txn_builder, TransactionBuilderAPI)

    receipt_builder = vm_block_instance.get_receipt_builder()
    assert receipt_builder is not None
    assert issubclass(receipt_builder, ReceiptBuilderAPI)

    bloom_filter = vm_block_instance.bloom_filter
    assert bloom_filter is not None
    assert isinstance(bloom_filter, BloomFilter)

    assert vm_block_instance.number == genesis_header.block_number == 0
    assert vm_block_instance.hash == genesis_header.hash
