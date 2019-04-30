import argparse
import json
import logging
from pathlib import Path
from typing import (
    Any,
)

from eth_utils import ValidationError

from eth.tools.logging import DEBUG2_LEVEL_NUM

from p2p.kademlia import Node
from p2p.validation import validate_enode_uri

from trinity import __version__
from trinity._utils.eip1085 import validate_raw_eip1085_genesis_config
from trinity.constants import (
    MAINNET_NETWORK_ID,
    ROPSTEN_NETWORK_ID,
)


class ValidateAndStoreEnodes(argparse.Action):
    def __call__(self,
                 parser: argparse.ArgumentParser,
                 namespace: argparse.Namespace,
                 value: Any,
                 option_string: str=None) -> None:
        if value is None:
            return

        validate_enode_uri(value)

        enode = Node.from_uri(value)

        if getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, [])
        enode_list = getattr(namespace, self.dest)
        enode_list.append(enode)


LOG_LEVEL_CHOICES = {
    # numeric versions
    '8': DEBUG2_LEVEL_NUM,
    '10': logging.DEBUG,
    '20': logging.INFO,
    '30': logging.WARNING,
    '40': logging.ERROR,
    '50': logging.CRITICAL,
    # string versions
    'DEBUG2': DEBUG2_LEVEL_NUM,
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARN': logging.WARNING,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}


def log_level_formatted_string() -> str:
    numeric_levels = [k for k in LOG_LEVEL_CHOICES.keys() if k.isdigit()]
    literal_levels = [k for k in LOG_LEVEL_CHOICES.keys() if not k.isdigit()]

    return (
        "LEVEL must be one of: "
        f"\n  {'/'.join(numeric_levels)} (numeric); "
        f"\n  {'/'.join(literal_levels).lower()} (lowercase); "
        f"\n  {'/'.join(literal_levels).upper()} (uppercase)."
    )


class ValidateAndStoreLogLevel(argparse.Action):
    def __call__(self,
                 parser: argparse.ArgumentParser,
                 namespace: argparse.Namespace,
                 value: Any,
                 option_string: str=None) -> None:
        if value is None:
            return

        raw_value = value.upper()

        # this is a global log level.
        if raw_value in LOG_LEVEL_CHOICES:
            path = None
            log_level = LOG_LEVEL_CHOICES[raw_value]
        else:
            path, _, raw_log_level = value.partition('=')

            if not path or not raw_log_level:
                raise argparse.ArgumentError(
                    self,
                    f"Invalid logging config: '{value}'.  Log level may be specified "
                    "as a global logging level using the syntax `--log-level "
                    "<LEVEL>`; or, to specify the logging level for an "
                    "individual logger, '--log-level "
                    "<LOGGER-NAME>=<LEVEL>'" + '\n' +
                    log_level_formatted_string()
                )

            try:
                log_level = LOG_LEVEL_CHOICES[raw_log_level.upper()]
            except KeyError:
                raise argparse.ArgumentError(self, (
                    f"Invalid logging level.  Got '{raw_log_level}'.",
                    log_level_formatted_string())
                )

        if getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, {})
        log_levels = getattr(namespace, self.dest)
        if path in log_levels:
            if path is None:
                raise argparse.ArgumentError(
                    self,
                    f"Global logging has already been configured to '{log_level}'.  The "
                    "global logging level may only be specified once."
                )
            else:
                raise argparse.ArgumentError(
                    self,
                    f"The logging level for '{path}' was provided more than once. "
                    "Please ensure the each name is provided only once"
                )
        log_levels[path] = log_level


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
trinity_parser = parser.add_argument_group('core')
logging_parser = parser.add_argument_group('logging')
network_parser = parser.add_argument_group('network')
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
    action=ValidateAndStoreLogLevel,
    dest="log_levels",
    metavar="LEVEL",
    help=(
        "Configure the logging level. " + log_level_formatted_string()
    ),
)
logging_parser.add_argument(
    '--stderr-log-level',
    dest="stderr_log_level",
    help=(
        "Configure the logging level for the stderr logging."
    ),
)
logging_parser.add_argument(
    '--file-log-level',
    dest="file_log_level",
    help=(
        "Configure the logging level for file-based logging."
    ),
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
    '--discv5',
    action='store_true',
    help=("Enable experimental v5 (topic) discovery mechanism"),
)

network_parser.add_argument(
    '--max-peers',
    help=(
        "Maximum number of network peers"
    ),
    type=int,
)


#
# Chain configuration
#
class EIP1085GenesisLoader(argparse.Action):
    def __call__(self,
                 parser: argparse.ArgumentParser,
                 namespace: argparse.Namespace,
                 value: Any,
                 option_string: str=None) -> None:
        genesis_file_path = Path(value)

        if not genesis_file_path.exists():
            raise argparse.ArgumentError(
                self,
                f"No genesis file found at: `{value}`"
            )

        try:
            genesis_config = json.load(genesis_file_path.open())
        except json.JSONDecodeError:
            raise argparse.ArgumentError(
                self,
                f"The genesis file at `{value}` is not valid json"
            )

        try:
            validate_raw_eip1085_genesis_config(genesis_config)
        except ValidationError as err:
            raise argparse.ArgumentError(
                self,
                f"The genesis file at `{value}` does not pass EIP1085 validation: {err}"
            )

        setattr(namespace, self.dest, genesis_config)


chain_parser.add_argument(
    '--genesis',
    help=(
        "File containing a custom genesis block header"
    ),
    action=EIP1085GenesisLoader,
)
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
        " or the filesystem path to the file which contains the nodekey"
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
