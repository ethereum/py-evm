# This might end up as a temporary place for this. The following code is
# included in the documentation (literalinclude!) and uses a more concise
# form of imports.

from argparse import ArgumentParser, _SubParsersAction

from trinity.extensibility import BaseIsolatedPlugin


# --START CLASS--
class PeerCountReporterPlugin(BaseIsolatedPlugin):

    @property
    def name(self) -> str:
        return "Peer Count Reporter"

    def configure_parser(self,
                         arg_parser: ArgumentParser,
                         subparser: _SubParsersAction) -> None:
        arg_parser.add_argument("--report-peer-count", type=bool, required=False)
