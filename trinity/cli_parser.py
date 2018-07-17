import argparse
from typing import (
    Any,
)

from eth.chains.mainnet import (
    MAINNET_NETWORK_ID,
)
from eth.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
)

from p2p.kademlia import Node

from trinity import __version__
from trinity.constants import (
    SYNC_FULL,
    SYNC_LIGHT,
)


class ValidateAndStoreEnodes(argparse.Action):
    def __call__(self,
                 parser: argparse.ArgumentParser,
                 namespace: argparse.Namespace,
                 values: Any,
                 option_string: str=None) -> None:
        if values is None:
            return

        enode = Node.from_uri(values)

        if getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, [])
        enode_list = getattr(namespace, self.dest)
        enode_list.append(enode)


DEFAULT_LOG_LEVEL = 'info'
LOG_LEVEL_CHOICES = (
    'trace',
    'debug',
    'info',
    'warning',
    'error',
    'critical',
)


parser = argparse.ArgumentParser(description='Trinity')

#
# subparser for sub commands
#
# Plugins may add subcommands with a `func` attribute
# to gain control over the main Trinity process
subparser = parser.add_subparsers(dest='subcommand')

#
# Argument Groups
#
trinity_parser = parser.add_argument_group('sync mode')
logging_parser = parser.add_argument_group('logging')
network_parser = parser.add_argument_group('network')
syncing_parser = parser.add_argument_group('sync mode')
chain_parser = parser.add_argument_group('chain')
debug_parser = parser.add_argument_group('debug')


#
# Trinity Globals
#
trinity_parser.add_argument('--version', action='version', version=__version__)
trinity_parser.add_argument(
    '--trinity-root-dir',
    help=(
        "The filesystem path to the base directory that trinity will store it's "
        "information.  Default: $XDG_DATA_HOME/.local/share/trinity"
    ),
)
trinity_parser.add_argument(
    '--port',
    type=int,
    required=False,
    default=30303,
    help=(
        "Port on which trinity should listen for incoming p2p/discovery connections. Default: 30303"
    ),
)


#
# Logging configuration
#
logging_parser.add_argument(
    '-l',
    '--log-level',
    choices=LOG_LEVEL_CHOICES,
    default=DEFAULT_LOG_LEVEL,
    help="Sets the logging level",
)

#
# Main parser for running trinity as a node.
#
networkid_parser = network_parser.add_mutually_exclusive_group()
networkid_parser.add_argument(
    '--network-id',
    type=int,
    help="Network identifier (1=Mainnet, 3=Ropsten)",
    default=MAINNET_NETWORK_ID,
)
networkid_parser.add_argument(
    '--ropsten',
    action='store_const',
    const=ROPSTEN_NETWORK_ID,
    dest='network_id',
    help=(
        "Ropsten network: pre configured proof-of-work test network.  Shortcut "
        "for `--networkid=3`"
    ),
)

network_parser.add_argument(
    '--preferred-node',
    action=ValidateAndStoreEnodes,
    dest="preferred_nodes",
    help=(
        "An enode address which will be 'preferred' above nodes found using the "
        "discovery protocol"
    ),
)

network_parser.add_argument(
    '--max-peers',
    help=(
        "Maximum number of network peers"
    ),
    type=int,
)


#
# Sync Mode
#
mode_parser = syncing_parser.add_mutually_exclusive_group()
mode_parser.add_argument(
    '--sync-mode',
    choices={SYNC_LIGHT, SYNC_FULL},
    default=SYNC_FULL,
)
mode_parser.add_argument(
    '--light',  # TODO: consider --sync-mode like geth.
    action='store_const',
    const=SYNC_LIGHT,
    dest='sync_mode',
    help="Shortcut for `--sync-mode=light`",
)


#
# Chain configuration
#
chain_parser.add_argument(
    '--data-dir',
    help=(
        "The directory where chain data is stored"
    ),
)
chain_parser.add_argument(
    '--nodekey',
    help=(
        "Hexadecimal encoded private key to use for the nodekey"
    )
)
chain_parser.add_argument(
    '--nodekey-path',
    help=(
        "The filesystem path to the file which contains the nodekey"
    )
)


#
# Debug configuration
#
debug_parser.add_argument(
    '--profile',
    action='store_true',
    help=(
        "Enables profiling via cProfile."
    ),
)

#
# Add `fix-unclean-shutdown` sub-command to trinity CLI
#
fix_unclean_shutdown_parser = subparser.add_parser(
    'fix-unclean-shutdown',
    help='close any dangling processes from a previous unclean shutdown',
)
