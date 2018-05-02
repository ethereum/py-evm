import argparse

from evm.chains.mainnet import (
    MAINNET_NETWORK_ID,
)
from evm.chains.ropsten import (
    ROPSTEN_NETWORK_ID,
)

from trinity.__version__ import __version__
from trinity.constants import (
    SYNC_FULL,
    SYNC_LIGHT,
)


DEFAULT_LOG_LEVEL = 'info'
LOG_LEVEL_CHOICES = (
    'debug',
    'info',
)


parser = argparse.ArgumentParser(description='Trinity')

#
# subparser for sub commands
#
subparser = parser.add_subparsers(dest='subcommand')

#
# Argument Groups
#
trinity_parser = parser.add_argument_group('sync mode')
logging_parser = parser.add_argument_group('logging')
network_parser = parser.add_argument_group('network')
syncing_parser = parser.add_argument_group('sync mode')
chain_parser = parser.add_argument_group('chain')


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
# Add `console` sub-command to trinity CLI.
#
console_parser = subparser.add_parser(
    'console', help='run the chain and start the trinity REPL')
console_parser.add_argument(
    '--vanilla-shell',
    action='store_true',
    default=False,
    help='start a native Python shell'
)


#
# Add `attach` sub-command to trinity CLI.
#
attach_parser = subparser.add_parser(
    'attach',
    help='open an REPL attached to a currently running chain',
)
attach_parser.add_argument(
    '--vanilla-shell',
    action='store_true',
    default=False,
    help='start a native Python shell'
)
