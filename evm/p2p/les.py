from evm.p2p.protocol import (
    Command,
    Protocol,
)


class Status(Command):
    _id = 0

    def handle(self, proto, data):
        proto.logger.debug("Got LES/Status msg")


class LESProtocol(Protocol):
    name = b'les'
    version = 1
    _commands = [Status]
    # FIXME: Need to find out the correct value for this
    cmd_length = 21
