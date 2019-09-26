import itertools
import random
from typing import Any, Generator, Tuple, Type

from p2p.abc import CommandAPI, ProtocolAPI
from p2p.commands import BaseCommand, NoneSerializationCodec
from p2p.protocol import BaseProtocol


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
                   command_id: int = None) -> Type[CommandAPI[None]]:
    # TODO: this needs to be simplified to account for codecs.
    if command_id is None:
        command_id = 0
    if name is None:
        name = CommandNameFactory()

    return type(
        name,
        (BaseCommand,),
        {
            'protocol_command_id': command_id,
            'serialization_codec': NoneSerializationCodec(),
        },
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
                    commands: Tuple[Type[CommandAPI[Any]], ...] = None) -> Type[ProtocolAPI]:
    if name is None:
        name = ProtocolNameFactory()
    if version is None:
        version = 1
    if commands is None:
        num_commands = random.randrange(1, 6)
        commands = tuple(
            CommandFactory(command_id=command_id)
            for command_id in range(num_commands)
        )

    return type(
        name.title(),
        (BaseProtocol,),
        {
            'name': name,
            'version': version,
            'commands': commands,
            'command_length': len(commands),
        },
    )
