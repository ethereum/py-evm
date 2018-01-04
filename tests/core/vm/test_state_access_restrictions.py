import pytest

from evm.exceptions import UnannouncedStateAccess

from evm.utils.numeric import (
    big_endian_to_int,
)
from evm.utils.state_access_restriction import (
    to_prefix_list_form,
)

from tests.core.fixtures import shard_chain  # noqa: F401


def test_balance_restriction(shard_chain):  # noqa: F811
    vm = shard_chain.get_vm()
    address = shard_chain.funded_address
    access_list = to_prefix_list_form([[address]])

    method_and_args = (
        ('get_balance', [address]),
        ('set_balance', [address, 1]),
        ('delta_balance', [address, 1]),
    )

    for method, args in method_and_args:
        with vm.state.state_db(access_list=access_list) as state_db:
            getattr(state_db, method)(*args)
        with pytest.raises(UnannouncedStateAccess):
            with vm.state.state_db(access_list=[]) as state_db:
                getattr(state_db, method)(*args)


def test_nonce_restriction(shard_chain):  # noqa: F811
    vm = shard_chain.get_vm()
    address = shard_chain.funded_address
    access_list = to_prefix_list_form([[address]])

    method_and_args = (
        ('get_nonce', [address]),
        ('set_nonce', [address, 1]),
        ('increment_nonce', [address]),
    )

    for method, args in method_and_args:
        with vm.state.state_db(access_list=access_list) as state_db:
            getattr(state_db, method)(*args)
        with pytest.raises(UnannouncedStateAccess):
            with vm.state.state_db(access_list=[]) as state_db:
                getattr(state_db, method)(*args)


def test_code_restriction(shard_chain):  # noqa: F811
    vm = shard_chain.get_vm()
    address = shard_chain.funded_address
    access_list = to_prefix_list_form([[address]])

    method_and_args = (
        ('get_code', [address]),
        ('set_code', [address, b'']),
        ('delete_code', [address])
    )

    for method, args in method_and_args:
        with vm.state.state_db(access_list=access_list) as state_db:
            getattr(state_db, method)(*args)
        with pytest.raises(UnannouncedStateAccess):
            with vm.state.state_db(access_list=[]) as state_db:
                getattr(state_db, method)(*args)


def test_storage_restriction(shard_chain):  # noqa: F811
    vm = shard_chain.get_vm()
    address = shard_chain.funded_address
    other_address = b'\xaa' * 20
    access_list = to_prefix_list_form([[address, b'\x00', b'\xff' * 32]])

    tests = (
        (True, 'get_storage', [address, big_endian_to_int(b'\x00' * 32)]),
        (True, 'get_storage', [address, big_endian_to_int(b'\x00' * 31 + b'\xff')]),
        (True, 'get_storage', [address, big_endian_to_int(b'\xff' * 32)]),
        (False, 'get_storage', [address, big_endian_to_int(b'\xaa' * 32)]),
        (False, 'get_storage', [other_address, big_endian_to_int(b'\x00' * 32)]),

        (True, 'set_storage', [address, big_endian_to_int(b'\x00' * 32), 0]),
        (True, 'set_storage', [address, big_endian_to_int(b'\x00' * 31 + b'\xff'), 0]),
        (True, 'set_storage', [address, big_endian_to_int(b'\xff' * 32), 0]),
        (False, 'set_storage', [address, big_endian_to_int(b'\xaa' * 32), 0]),
        (False, 'set_storage', [other_address, big_endian_to_int(b'\x00' * 32), 0]),
    )

    for valid, method, args in tests:
        if valid:
            with vm.state.state_db(access_list=access_list) as state_db:
                getattr(state_db, method)(*args)
        else:
            with pytest.raises(UnannouncedStateAccess):
                with vm.state.state_db(access_list=access_list) as state_db:
                    getattr(state_db, method)(*args)

        # without access list everything is invalid
        with pytest.raises(UnannouncedStateAccess):
            with vm.state.state_db(access_list=[]) as state_db:
                getattr(state_db, method)(*args)
