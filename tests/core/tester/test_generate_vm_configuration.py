import pytest

import enum

from evm.vm.flavors.tester import (
    _generate_vm_configuration,
)


class Forks(enum.Enum):
    Frontier = 0
    Homestead = 1
    EIP150 = 2


@pytest.mark.parametrize(
    "kwargs,expected",
    (
        (
            dict(),
            ((0, Forks.EIP150),),
        ),
        (
            dict(eip150_start_block=1),
            ((0, Forks.Homestead), (1, Forks.EIP150)),
        ),
        (
            dict(homestead_start_block=1),
            ((0, Forks.Frontier), (1, Forks.Homestead)),
        ),
        (
            dict(homestead_start_block=1, dao_start_block=2),
            ((0, Forks.Frontier), (1, Forks.Homestead)),
        ),
        (
            dict(homestead_start_block=1, dao_start_block=False),
            ((0, Forks.Frontier), (1, Forks.Homestead)),
        ),
        (
            dict(homestead_start_block=1, eip150_start_block=2),
            ((0, Forks.Frontier), (1, Forks.Homestead), (2, Forks.EIP150)),
        ),
    ),
)
def test_generate_vm_configuration(kwargs, expected):
    actual = _generate_vm_configuration(**kwargs)
    assert len(actual) == len(expected)

    for left, right in zip(actual, expected):
        left_block, left_vm = left
        right_block, right_vm = right

        assert left_block == right_block

        if right_vm == Forks.Frontier:
            assert 'Frontier' in left_vm.__name__
        elif right_vm == Forks.Homestead:
            assert 'Homestead' in left_vm.__name__
            dao_start_block = kwargs.get('dao_start_block')
            if dao_start_block is False:
                assert left_vm.support_dao_fork is False
            elif dao_start_block is None:
                assert left_vm.support_dao_fork is True
                assert left_vm.dao_fork_block_number == right_block
            else:
                assert left_vm.support_dao_fork is True
                assert left_vm.dao_fork_block_number == dao_start_block
        elif right_vm == Forks.EIP150:
            assert 'EIP150' in left_vm.__name__
        else:
            assert False, "Invariant"
