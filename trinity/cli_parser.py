import argparse

from trinity.__version__ import __version__


DEFAULT_LOG_LEVEL = 'info'
LOG_LEVEL_CHOICES = (
    'debug',
    'info',
)


parser = argparse.ArgumentParser(description='Trinity')

#
# Version: `trinity --version`
#
parser.add_argument('--version', action='version', version=__version__)

#
# Logging configuration
#
parser.add_argument(
    '-l',
    '--log-level',
    choices=LOG_LEVEL_CHOICES,
    default=DEFAULT_LOG_LEVEL,
    help="Sets the logging level",
)

#
# Main parser for running trinity as a node.
#
parser.add_argument(
    '--ropsten',
    action='store_true',
    help="Ropsten network: pre configured proof-of-work test network",
)
parser.add_argument(
    '--light',  # TODO: consider --sync-mode like geth.
    action='store_true',
)
parser.add_argument(
    '--trinity-root-dir',
    help=(
        "The filesystem path to the base directory that trinity will store it's "
        "information.  Default: $XDG_DATA_HOME/.local/share/trinity"
    ),
)
parser.add_argument(
    '--data-dir',
    help=(
        "The directory where chain data is stored"
    ),
)
parser.add_argument(
    '--nodekey',
    help=(
        "Hexadecimal encoded private key to use for the nodekey"
    )
)
parser.add_argument(
    '--nodekey-path',
    help=(
        "The filesystem path to the file which contains the nodekey"
    )
)

# setup the subparser for sub commands
subparser = parser.add_subparsers(dest='subcommand')


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
