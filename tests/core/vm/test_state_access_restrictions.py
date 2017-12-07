import pytest

from evm.exceptions import UnannouncedStateAccess

from evm.utils.numeric import (
    big_endian_to_int,
)
from evm.utils.state_access_restriction import (
    to_prefix_list_form,
)

from tests.core.fixtures import chain  # noqa: F401


def test_balance_read_restriction(chain):  # noqa: F811
    vm = chain.get_vm()
    address = chain.funded_address
    read_and_write_list = (to_prefix_list_form([[address]]), [])

    with vm.state_db(read_and_write_list=read_and_write_list) as state_db:
        state_db.get_balance(address)
    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=([], [])) as state_db:
            state_db.get_balance(address)


def test_balance_write_restriction(chain):  # noqa: F811
    vm = chain.get_vm()
    address = chain.funded_address
    write_list = to_prefix_list_form([[address]])
    read_list = write_list

    with vm.state_db(read_and_write_list=([], write_list)) as state_db:
        state_db.set_balance(address, 0)
    with vm.state_db(read_and_write_list=(read_list, write_list)) as state_db:
        state_db.delta_balance(address, 1)

    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=([], [])) as state_db:
            state_db.set_balance(address, 0)
    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=(read_list, [])) as state_db:
            state_db.delta_balance(address, 1)
    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=([], write_list)) as state_db:
            state_db.delta_balance(address, 1)


def test_nonce_read_restriction(chain):  # noqa: F811
    vm = chain.get_vm()
    address = chain.funded_address
    read_and_write_list = (to_prefix_list_form([[address]]), [])

    with vm.state_db(read_and_write_list=read_and_write_list) as state_db:
        state_db.get_nonce(address)
    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=([], [])) as state_db:
            state_db.get_nonce(address)


def test_nonce_write_restriction(chain):  # noqa: F811
    vm = chain.get_vm()
    address = chain.funded_address
    write_list = to_prefix_list_form([[address]])
    read_list = write_list

    with vm.state_db(read_and_write_list=([], write_list)) as state_db:
        state_db.set_nonce(address, 0)
    with vm.state_db(read_and_write_list=(read_list, write_list)) as state_db:
        state_db.increment_nonce(address)

    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=([], [])) as state_db:
            state_db.set_nonce(address, 0)
    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=(read_list, [])) as state_db:
            state_db.increment_nonce(address)
    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=([], write_list)) as state_db:
            state_db.increment_nonce(address)


def test_code_read_restriction(chain):  # noqa: F811
    vm = chain.get_vm()
    address = chain.funded_address
    read_and_write_list = (to_prefix_list_form([[address]]), [])

    with vm.state_db(read_and_write_list=read_and_write_list) as state_db:
        state_db.get_code(address)
        state_db.get_code_hash(address)
    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=([], [])) as state_db:
            state_db.get_code(address)
    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=([], [])) as state_db:
            state_db.get_code_hash(address)


def test_code_write_restriction(chain):  # noqa: F811
    vm = chain.get_vm()
    address = chain.funded_address
    read_and_write_list = ([], to_prefix_list_form([[address]]))

    with vm.state_db(read_and_write_list=read_and_write_list) as state_db:
        state_db.set_code(address, b'')
        state_db.delete_code(address)
    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=([], [])) as state_db:
            state_db.set_code(address, b'')
    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=([], [])) as state_db:
            state_db.delete_code(address)


def test_storage_read_restriction(chain):  # noqa: F811
    vm = chain.get_vm()
    address = chain.funded_address
    other_address = b'\xaa' * 20
    read_and_write_list = (to_prefix_list_form([[address, b'\x00', b'\xff' * 32]]), [])

    with vm.state_db(read_and_write_list=read_and_write_list) as state_db:
        state_db.get_storage(address, big_endian_to_int(b'\x00' * 32))
        state_db.get_storage(address, big_endian_to_int(b'\x00' * 31 + b'\xff'))
        state_db.get_storage(address, big_endian_to_int(b'\xff' * 32))

    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=read_and_write_list) as state_db:
            state_db.get_storage(other_address, big_endian_to_int(b'\x00' * 32))

    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=read_and_write_list) as state_db:
            state_db.get_storage(address, big_endian_to_int(b'\xaa' * 32))

    slot_keys = [b'\x00' * 32, b'\x00' * 31 + b'\xff', b'\xff' * 32]
    for slot in [big_endian_to_int(key) for key in slot_keys]:
        with pytest.raises(UnannouncedStateAccess):
            with vm.state_db(read_and_write_list=([], [])) as state_db:
                state_db.get_storage(address, slot)


def test_storage_write_restriction(chain):  # noqa: F811
    vm = chain.get_vm()
    address = chain.funded_address
    other_address = b'\xaa' * 20
    read_and_write_list = ([], to_prefix_list_form([[address, b'\x00', b'\xff' * 32]]))

    with vm.state_db(read_and_write_list=read_and_write_list) as state_db:
        state_db.set_storage(address, big_endian_to_int(b'\x00' * 32), 0)
        state_db.set_storage(address, big_endian_to_int(b'\x00' * 31 + b'\xff'), 0)
        state_db.set_storage(address, big_endian_to_int(b'\xff' * 32), 0)

    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=read_and_write_list) as state_db:
            state_db.set_storage(other_address, big_endian_to_int(b'\x00' * 32), 0)

    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=read_and_write_list) as state_db:
            state_db.set_storage(address, big_endian_to_int(b'\xaa' * 32), 0)

    slot_keys = [b'\x00' * 32, b'\x00' * 31 + b'\xff', b'\xff' * 32]
    for slot in [big_endian_to_int(key) for key in slot_keys]:
        with pytest.raises(UnannouncedStateAccess):
            with vm.state_db(read_and_write_list=([], [])) as state_db:
                state_db.set_storage(address, slot, 0)

    with pytest.raises(UnannouncedStateAccess):
        with vm.state_db(read_and_write_list=read_and_write_list) as state_db:
            state_db.delete_storage(address)

    with vm.state_db(read_and_write_list=([], to_prefix_list_form([[address, b'']]))) as state_db:
        state_db.delete_storage(address)
