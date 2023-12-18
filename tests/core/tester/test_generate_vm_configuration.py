import enum

import pytest

from eth.chains.tester import (
    _generate_vm_configuration,
)
from eth.vm.forks.frontier import (
    FrontierVM,
)


class Forks(enum.Enum):
    Custom = "CustomFrontier"
    Frontier = "Frontier"
    Homestead = "Homestead"
    TangerineWhistle = "TangerineWhistle"
    SpuriousDragon = "SpuriousDragon"
    Byzantium = "Byzantium"
    Constantinople = "Constantinople"
    Petersburg = "Petersburg"
    Istanbul = "Istanbul"
    MuirGlacier = "MuirGlacier"
    Berlin = "Berlin"
    London = "London"
    ArrowGlacier = "ArrowGlacier"
    GrayGlacier = "GrayGlacier"
    Paris = "Paris"


class CustomFrontierVM(FrontierVM):
    pass


@pytest.mark.parametrize(
    "args,kwargs,expected",
    (
        (
            (),
            {},
            ((0, Forks.Paris),),
        ),
        (
            ((0, "tangerine-whistle"), (1, "spurious-dragon")),
            {},
            ((0, Forks.TangerineWhistle), (1, Forks.SpuriousDragon)),
        ),
        (
            ((1, "tangerine-whistle"), (2, "spurious-dragon")),
            {},
            (
                (0, Forks.Frontier),
                (1, Forks.TangerineWhistle),
                (2, Forks.SpuriousDragon),
            ),
        ),
        (
            ((0, CustomFrontierVM), (1, "spurious-dragon")),
            {},
            ((0, Forks.Custom), (1, Forks.SpuriousDragon)),
        ),
        (
            ((0, "homestead"), (1, "tangerine-whistle"), (2, "spurious-dragon")),
            {},
            (
                (0, Forks.Homestead),
                (1, Forks.TangerineWhistle),
                (2, Forks.SpuriousDragon),
            ),
        ),
        (
            (
                (0, "frontier"),
                (1, "homestead"),
                (2, "tangerine-whistle"),
                (3, "spurious-dragon"),
            ),
            {},
            (
                (0, Forks.Frontier),
                (1, Forks.Homestead),
                (2, Forks.TangerineWhistle),
                (3, Forks.SpuriousDragon),
            ),
        ),
        (
            ((0, "frontier"), (1, "homestead"), (3, "spurious-dragon")),
            {},
            (
                (0, Forks.Frontier),
                (1, Forks.Homestead),
                (3, Forks.SpuriousDragon),
            ),
        ),
        (
            ((0, "homestead"), (1, "tangerine-whistle")),
            {},
            ((0, Forks.Homestead), (1, Forks.TangerineWhistle)),
        ),
        (
            ((0, "frontier"), (1, "homestead")),
            {},
            ((0, Forks.Frontier), (1, Forks.Homestead)),
        ),
        (
            ((1, "homestead"),),
            {},
            ((0, Forks.Frontier), (1, Forks.Homestead)),
        ),
        (
            ((0, "frontier"), (1, "homestead")),
            {"dao_start_block": 2},
            ((0, Forks.Frontier), (1, Forks.Homestead)),
        ),
        (
            ((0, "frontier"), (1, "homestead")),
            {"dao_start_block": False},
            ((0, Forks.Frontier), (1, Forks.Homestead)),
        ),
        (
            ((0, "frontier"), (1, "homestead"), (2, "tangerine-whistle")),
            {},
            ((0, Forks.Frontier), (1, Forks.Homestead), (2, Forks.TangerineWhistle)),
        ),
        (
            (
                (0, "frontier"),
                (1, "homestead"),
                (2, "tangerine-whistle"),
                (3, "byzantium"),
            ),
            {},
            (
                (0, Forks.Frontier),
                (1, Forks.Homestead),
                (2, Forks.TangerineWhistle),
                (3, Forks.Byzantium),
            ),
        ),
        (
            (
                (0, "frontier"),
                (1, "homestead"),
                (2, "tangerine-whistle"),
                (3, "byzantium"),
                (5, "petersburg"),
                (6, "istanbul"),
                (7, "muir-glacier"),
                (8, "berlin"),
                (9, "london"),
                (10, "arrow-glacier"),
                (11, "gray-glacier"),
                (12, "paris"),
            ),
            {},
            (
                (0, Forks.Frontier),
                (1, Forks.Homestead),
                (2, Forks.TangerineWhistle),
                (3, Forks.Byzantium),
                (5, Forks.Petersburg),
                (6, Forks.Istanbul),
                (7, Forks.MuirGlacier),
                (8, Forks.Berlin),
                (9, Forks.London),
                (10, Forks.ArrowGlacier),
                (11, Forks.GrayGlacier),
                (12, Forks.Paris),
            ),
        ),
    ),
)
def test_generate_vm_configuration(args, kwargs, expected):
    actual = _generate_vm_configuration(*args, **kwargs)

    assert len(actual) == len(expected)

    for left, right in zip(actual, expected):
        left_block, left_vm = left
        right_block, right_vm = right

        assert left_block == right_block

        assert right_vm.value in left_vm.__name__

        if right_vm == Forks.Homestead:
            dao_start_block = kwargs.get("dao_start_block")
            if dao_start_block is False:
                assert left_vm.support_dao_fork is False
            elif dao_start_block is None:
                assert left_vm.support_dao_fork is True
                assert left_vm.get_dao_fork_block_number() == right_block
            else:
                assert left_vm.support_dao_fork is True
                assert left_vm.get_dao_fork_block_number() == dao_start_block
