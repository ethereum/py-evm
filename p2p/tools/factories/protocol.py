import itertools
import random
from typing import Any, Generator, Iterable, Tuple, Type

from rlp import sedes

from eth_utils import to_tuple

from p2p.abc import CommandAPI, ProtocolAPI
from p2p.protocol import Command, Protocol


STRUCTURE_SEDES = (
    sedes.big_endian_int,
    sedes.binary,
)


@to_tuple
def StructureFactory(high_water_mark: int = 4,
                     ) -> Iterable[Tuple[str, Any]]:
    for idx in range(high_water_mark):
        name = f"field_{idx}"
        sedes = random.choice(STRUCTURE_SEDES)
        yield (name, sedes)
        if random.randrange(idx, high_water_mark + 2) >= high_water_mark:
            break


ACTIONS = (
    'dig',
    'run',
    'jump',
    'create',
    'destroy',
    'fill',
    'build',
    'create',
    'kill',
    'finish',
    'hello',
    'goodbye',
    'connect',
    'disconnect',
    'activate',
    'disable',
    'enable',
    'validate',
    'post',
    'get',
)


ANIMALS = (
    'dog',
    'cat',
    'bird',
    'fox',
    'panda',
    'unicorn',
    'bear',
    'eagle',
)


COLORS = (
    'red',
    'orange',
    'yellow',
    'green',
    'blue',
    'purple',
    'pink',
    'brown',
    'black',
    'white',
)


def _command_name_enumerator() -> Generator[str, None, None]:
    while True:
        for action in ACTIONS:
            yield action.title()
        for action, animal in itertools.product(ACTIONS, ANIMALS):
            yield f"{action.title()}{animal.title()}"


_command_name_iter = _command_name_enumerator()


def CommandNameFactory() -> str:
    return next(_command_name_iter)


def CommandFactory(name: str = None,
                   cmd_id: int = None,
                   structure: Tuple[Tuple[str, Any], ...] = None) -> Type[CommandAPI]:
    if structure is None:
        structure = StructureFactory()
    if cmd_id is None:
        cmd_id = 0
    if name is None:
        name = CommandNameFactory()

    return type(
        name,
        (Command,),
        {'_cmd_id': cmd_id, 'structure': structure},
    )


def _protocol_name_enumerator() -> Generator[str, None, None]:
    while True:
        for color, animal in itertools.product(COLORS, ANIMALS):
            yield f"{color}_{animal}"


_protocol_name_iter = _protocol_name_enumerator()


def ProtocolNameFactory() -> str:
    return next(_protocol_name_iter)


def ProtocolFactory(name: str = None,
                    version: int = None,
                    commands: Tuple[Type[CommandAPI], ...] = None) -> Type[ProtocolAPI]:
    if name is None:
        name = ProtocolNameFactory()
    if version is None:
        version = 1
    if commands is None:
        num_commands = random.randrange(1, 6)
        commands = tuple(
            CommandFactory(cmd_id=cmd_id)
            for cmd_id in range(num_commands)
        )

    cmd_length = len(commands)

    return type(
        name.title(),
        (Protocol,),
        {'name': name, 'version': version, '_commands': commands, 'cmd_length': cmd_length},
    )
