import pytest

from eth_utils import (
    to_canonical_address,
)

from eth.precompiles.ecrecover import (
    ecrecover,
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


CANONICAL_ADDRESS_A = to_canonical_address("0x0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6")
CANONICAL_ADDRESS_B = to_canonical_address("0xcd1722f3947def4cf144679da39c4c32bdc35681")
BAD_DATA = b'\x60\x60\x5a\x1a\x7f\x6b\x8d\x2c\x81\xb1\x1b\x2d\x69\x95\x28\xdd\xe4\x88\xdb\xdf\x2f\x94\x29\x3d\x0d\x33\xc3\x2e\x34\x7f\x25\x5f\xa4\xa6\xc1\xf0\xa9\x60\x00\x52\x7f\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1b\x60\x20\x52\x7f\x79\xbe\x66\x7e\xf9\xdc\xbb\xac\x55\xa0\x62\x95\xce\x87\x0b\x07\x02\x9b\xfc\xdb\x2d\xce\x28\xd9\x59\xf2\x81\x5b\x16\xf8\x17\x98\x60\x40\x52\x7f\x6b\x8d\x2c\x81\xb1\x1b\x2d\x69\x95\x28\xdd\xe4\x88\xdb\xdf\x2f\x94\x29\x3d\x0d\x33\xc3\x2e\x34\x7f\x25\x5f\xa4\xa6\xc1\xf0\xa9\x60\x60\x52\x60\x20\x60\x80\x60\x80\x60\x00\x60\x00\x60\x01\x62\x98\x96\x80\xf1\x60\x40\x52\x5b\x36\x3d\x3d\x60\x21\x5a\x07'  # noqa: E501

msg = b'\x6b\x8d\x2c\x81\xb1\x1b\x2d\x69\x95\x28\xdd\xe4\x88\xdb\xdf\x2f\x94\x29\x3d\x0d\x33\xc3\x2e\x34\x7f\x25\x5f\xa4\xa6\xc1\xf0\xa9'  # noqa: E501
v = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1c'  # noqa: E501
r = b'\x53\x56\x92\x27\x4f\x15\x24\x34\x00\x2a\x7c\x4c\x7d\x7c\xd0\x16\xea\x3e\x2d\x70\x2f\x2d\x2f\xd5\xb3\x32\x64\x6a\x9e\x40\x9a\x6b'  # noqa: E501
s = b'\x1f\x59\x24\xf5\x9c\x6d\x77\x66\xa6\x93\x17\xa3\xdf\x72\x9d\x8b\x61\x3c\x67\xaa\xf2\xfe\x06\x13\x39\x8b\x9f\x94\x4b\x98\x8e\xbd'  # noqa: E501

GOOD_DATA = msg + v + r + s


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
def transaction_context():
    tx_context = DummyTransactionContext(
        gas_price=1,
        origin=CANONICAL_ADDRESS_B,
    )
    return tx_context


def test_ecrecover_validates_length_of_data():
    message = Message(
        to=CANONICAL_ADDRESS_A,
        sender=CANONICAL_ADDRESS_B,
        value=100,
        data=BAD_DATA,
        code=BAD_DATA,
        gas=100000000,
    )
    computation = DummyComputation(
        state=None,
        message=message,
        transaction_context=transaction_context,
    )
    return_val = ecrecover(computation)
    assert return_val.output == b''


def test_ecrecover():
    message = Message(
        to=CANONICAL_ADDRESS_A,
        sender=CANONICAL_ADDRESS_B,
        value=100,
        data=GOOD_DATA,
        code=GOOD_DATA,
        gas=100000000000,
    )
    computation = DummyComputation(
        state=None,
        message=message,
        transaction_context=transaction_context,
    )
    expected_output = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x83\x17\x080\x8eM\xb9k\xfe/\xe5O\xe0+\xb5c$\xab\xa6w'  # noqa: E501
    assert ecrecover(computation).is_success
    assert ecrecover(computation).output == expected_output
