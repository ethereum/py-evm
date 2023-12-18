from eth_utils import (
    ValidationError,
)
import pytest

from eth.exceptions import (
    Revert,
    VMError,
)
from eth.vm.computation import (
    BaseComputation,
)
from eth.vm.message import (
    Message,
)
from eth.vm.transaction_context import (
    BaseTransactionContext,
)


class DummyComputation(BaseComputation):
    @classmethod
    def apply_message(cls, *args):
        return cls(*args)

    @classmethod
    def apply_create_message(cls, *args):
        return cls(*args)


class DummyTransactionContext(BaseTransactionContext):
    def get_intrinsic_gas(self):
        return 0


@pytest.fixture
def message(canonical_address_a, canonical_address_b):
    message = Message(
        to=canonical_address_a,
        sender=canonical_address_b,
        value=100,
        data=b"",
        code=b"",
        gas=100,
    )
    return message


@pytest.fixture
def computation(message, transaction_context):
    computation = DummyComputation(
        state=None,
        message=message,
        transaction_context=transaction_context,
    )
    return computation


@pytest.fixture
def child_message(computation, canonical_address_b):
    child_message = computation.prepare_child_message(
        gas=100, to=canonical_address_b, value=200, data=b"", code=b""
    )
    return child_message


def test_is_origin_computation(computation, transaction_context, canonical_address_a):
    assert computation.is_origin_computation
    message2 = Message(
        to=canonical_address_a,
        # Different sender than the tx context origin
        sender=canonical_address_a,
        value=100,
        data=b"",
        code=b"",
        gas=100,
    )
    computation2 = DummyComputation(
        state=None,
        message=message2,
        transaction_context=transaction_context,
    )
    assert not computation2.is_origin_computation


def test_prepare_child_message(computation, child_message):
    assert computation.msg.depth == 0
    assert child_message.depth == 1
    assert computation.msg.storage_address == child_message.sender


def test_extend_memory_start_position_must_be_uint256(computation):
    with pytest.raises(ValidationError):
        computation.extend_memory("1", 1)
    with pytest.raises(ValidationError):
        computation.extend_memory(-1, 1)


def test_extend_memory_size_must_be_uint256(computation):
    with pytest.raises(ValidationError):
        computation.extend_memory(1, "1")
    with pytest.raises(ValidationError):
        computation.extend_memory(1, -1)


def test_extend_memory_stays_the_same_if_size_is_0(computation):
    assert len(computation._memory._bytes) == 0
    computation.extend_memory(1, 0)
    assert len(computation._memory._bytes) == 0


def test_extend_memory_increases_memory_by_32(computation):
    assert computation._gas_meter.gas_remaining == 100
    computation.extend_memory(0, 1)
    assert len(computation._memory._bytes) == 32
    # 32 bytes of memory cost 3 gas
    assert computation._gas_meter.gas_remaining == 97


def test_extend_memory_doesnt_increase_until_32_bytes_are_used(computation):
    computation.extend_memory(0, 1)
    computation.extend_memory(1, 1)
    assert len(computation._memory._bytes) == 32
    computation.extend_memory(2, 32)
    assert len(computation._memory._bytes) == 64
    assert computation._gas_meter.gas_remaining == 94


def test_register_accounts_for_deletion_raises_if_address_isnt_canonical(
    computation, normalized_address_a
):
    with pytest.raises(ValidationError):
        computation.register_account_for_deletion(normalized_address_a)


def test_register_accounts_for_deletion_cannot_register_the_same_address_twice(
    computation, canonical_address_a
):
    computation.register_account_for_deletion(canonical_address_a)
    with pytest.raises(ValueError):
        computation.register_account_for_deletion(canonical_address_a)


def test_register_accounts_for_deletion(
    computation, canonical_address_a, canonical_address_b
):
    computation.register_account_for_deletion(canonical_address_a)
    assert (
        computation.accounts_to_delete[computation.msg.storage_address]
        == canonical_address_a
    )
    # Another account can be registered for deletion
    computation.msg.storage_address = canonical_address_b
    computation.register_account_for_deletion(canonical_address_a)


def test_get_accounts_for_deletion_starts_empty(computation):
    assert computation.get_accounts_for_deletion() == ()


def test_get_accounts_for_deletion_returns(
    computation, canonical_address_a, canonical_address_b
):
    computation.register_account_for_deletion(canonical_address_a)
    # Get accounts for deletion returns the correct account
    assert computation.get_accounts_for_deletion() == (
        (canonical_address_a, canonical_address_a),
    )
    # Get accounts for deletion can return multiple accounts
    computation.msg.storage_address = canonical_address_b
    computation.register_account_for_deletion(canonical_address_b)
    accounts_for_deletion = sorted(
        computation.get_accounts_for_deletion(), key=lambda item: item[0]
    )
    assert canonical_address_a == accounts_for_deletion[0][0]
    assert canonical_address_b == accounts_for_deletion[1][0]


def test_add_log_entry_starts_empty(computation):
    assert computation.get_log_entries() == ()


def test_add_log_entry_raises_if_address_isnt_canonical(
    computation, normalized_address_a
):
    with pytest.raises(ValidationError):
        computation.add_log_entry(normalized_address_a, [1, 2, 3], b"")


def test_add_log_entry_raises_if_topic_elements_arent_uint256(
    computation, canonical_address_a
):
    with pytest.raises(ValidationError):
        computation.add_log_entry(canonical_address_a, [-1, 2, 3], b"")
    with pytest.raises(ValidationError):
        computation.add_log_entry(canonical_address_a, ["1", 2, 3], b"")


def test_add_log_entry_raises_if_data_isnt_in_bytes(computation, canonical_address_a):
    with pytest.raises(ValidationError):
        computation.add_log_entry(canonical_address_a, [1, 2, 3], 1)
    with pytest.raises(ValidationError):
        computation.add_log_entry(canonical_address_a, [1, 2, 3], "")


def test_add_log_entry(computation, canonical_address_a):
    # Adds log entry to log entries
    computation.add_log_entry(canonical_address_a, [1, 2, 3], b"")
    assert computation.get_log_entries() == tuple(
        [(b"\x0fW.R\x95\xc5\x7f\x15\x88o\x9b&>/m-l\x7b^\xc6", [1, 2, 3], b"")]
    )
    # Can add multiple entries
    computation.add_log_entry(canonical_address_a, [4, 5, 6], b"2")
    computation.add_log_entry(canonical_address_a, [7, 8, 9], b"3")

    assert len(computation.get_log_entries()) == 3


def test_get_log_entries(computation, canonical_address_a):
    computation.add_log_entry(canonical_address_a, [1, 2, 3], b"")
    assert computation.get_log_entries() == (
        (b"\x0fW.R\x95\xc5\x7f\x15\x88o\x9b&>/m-l\x7b^\xc6", [1, 2, 3], b""),
    )


def test_get_log_entries_order_with_children(
    computation, child_message, canonical_address_a
):
    parent_log = (canonical_address_a, [1, 2, 3], b"")
    parent_log2 = (canonical_address_a, [4, 5, 6], b"2")
    child_log = (canonical_address_a, [1, 2, 3], b"child")
    computation.add_log_entry(*parent_log)
    child_computation = computation.apply_child_computation(child_message)
    # Pretend the child computation logged something.
    child_computation.add_log_entry(*child_log)
    computation.add_log_entry(*parent_log2)

    logs = computation.get_log_entries()

    # The returned log entries must be in the same order they were generated.
    assert len(logs) == 3
    assert logs[0] == parent_log
    assert logs[1] == child_log
    assert logs[2] == parent_log2


def test_get_log_entries_with_vmerror(computation, canonical_address_a):
    # Trigger an out of gas error causing get log entries to be ()
    computation.add_log_entry(canonical_address_a, [1, 2, 3], b"")
    with computation:
        raise VMError("Triggered VMError for tests")
    assert computation.is_error
    assert computation.get_log_entries() == ()


def test_get_log_entries_with_revert(computation, canonical_address_a):
    # Trigger an out of gas error causing get log entries to be ()
    computation.add_log_entry(canonical_address_a, [1, 2, 3], b"")
    with computation:
        raise Revert("Triggered VMError for tests")
    assert computation.is_error
    assert computation.get_log_entries() == ()


def test_get_gas_refund(computation):
    computation._gas_meter.refund_gas(100)
    assert computation.get_gas_refund() == 100


def test_get_gas_refund_with_vmerror(computation):
    # Trigger an out of gas error causing get gas refund to be 0
    computation._gas_meter.refund_gas(100)
    with computation:
        raise VMError("Triggered VMError for tests")
    assert computation.is_error
    assert computation.get_gas_refund() == 0


def test_get_gas_refund_with_revert(computation):
    # Trigger an out of gas error causing get gas refund to be 0
    computation._gas_meter.refund_gas(100)
    with computation:
        raise Revert("Triggered VMError for tests")
    assert computation.is_error
    assert computation.get_gas_refund() == 0


def test_output(computation):
    computation.output = b"1"
    assert computation.output == b"1"


def test_output_with_vmerror(computation):
    # Trigger an out of gas error causing output to be b''
    computation.output = b"1"
    with computation:
        raise VMError("Triggered VMError for tests")
    assert computation.is_error
    assert computation.output == b""


def test_output_with_revert(computation):
    # Trigger an out of gas error causing output to be b''
    computation.output = b"1"
    with computation:
        raise Revert("Triggered VMError for tests")
    assert computation.is_error
    assert computation.output == b"1"


def test_get_gas_remaining(computation):
    assert computation.get_gas_remaining() == 100


def test_get_gas_remaining_with_vmerror(computation):
    assert computation.get_gas_remaining() == 100
    # Trigger an out of gas error causing get gas remaining to be 0
    with computation:
        raise VMError("Triggered VMError for tests")
    assert computation.is_error
    assert computation.get_gas_remaining() == 0


def test_get_gas_remaining_with_revert(computation):
    assert computation.get_gas_remaining() == 100
    # Trigger an out of gas error causing get gas remaining to be 0
    with computation:
        raise Revert("Triggered VMError for tests")
    assert computation.is_error
    assert computation.get_gas_remaining() == 100


def test_get_gas_used(computation):
    # User 3 gas to extend memory
    computation.consume_gas(3, reason="testing")
    computation.consume_gas(2, reason="testing")
    assert computation.get_gas_used() == 5


def test_get_gas_used_with_vmerror(computation):
    # Trigger an out of gas error causing get gas used to be 150
    computation.consume_gas(3, reason="testing")
    computation.consume_gas(2, reason="testing")
    with computation:
        raise VMError("Triggered VMError for tests")
    assert computation.is_error
    assert computation.get_gas_used() == 100


def test_get_gas_used_with_revert(computation):
    # Trigger an out of gas error causing get gas used to be 150
    computation.consume_gas(3, reason="testing")
    computation.consume_gas(2, reason="testing")
    with computation:
        raise Revert("Triggered VMError for tests")
    assert computation.is_error
    assert computation.get_gas_used() == 5


def test_should_burn_gas_with_vm_error(computation):
    assert computation.get_gas_remaining() == 100
    # Trigger an out of gas error causing remaining gas to be 0
    with computation:
        raise VMError("Triggered VMError for tests")
    assert computation.should_burn_gas
    assert computation.get_gas_used() == 100
    assert computation.get_gas_remaining() == 0


def test_should_burn_gas_with_revert(computation):
    assert computation.get_gas_remaining() == 100
    # Trigger a Revert which should not burn gas
    with computation:
        raise Revert("Triggered VMError for tests")
    assert not computation.should_burn_gas
    assert computation.get_gas_used() == 0
    assert computation.get_gas_remaining() == 100


def test_should_erase_return_data_with_vm_error(computation):
    assert computation.get_gas_remaining() == 100
    computation.return_data = b"\x1337"
    # Trigger a VMError which should erase the return data
    with computation:
        raise VMError("Triggered VMError for tests")
    assert computation.should_erase_return_data
    assert computation.return_data == b""


def test_should_erase_return_data_with_revert(computation):
    assert computation.get_gas_remaining() == 100
    computation.return_data = b"\x1337"
    # Trigger a Revert which should not erase return data
    with computation:
        raise Revert("Triggered VMError for tests")
    assert not computation.should_erase_return_data
    assert computation.return_data == b"\x1337"
