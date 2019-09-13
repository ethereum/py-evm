from p2p.exchange import BaseExchangeHandler

from trinity.protocol.bcc.exchanges import BeaconBlocksExchange


class BCCExchangeHandler(BaseExchangeHandler):
    _exchange_config = {
        "get_beacon_blocks": BeaconBlocksExchange,
    }

    # These are needed only to please mypy.
    get_beacon_blocks: BeaconBlocksExchange
