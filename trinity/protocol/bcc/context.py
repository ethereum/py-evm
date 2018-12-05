from p2p.peer import BasePeerContext

from eth.beacon.db.chain import BaseBeaconChainDB


class BeaconContext(BasePeerContext):

    def __init__(self, chain_db: BaseBeaconChainDB, network_id: int) -> None:
        self.chain_db = chain_db
        self.network_id = network_id
