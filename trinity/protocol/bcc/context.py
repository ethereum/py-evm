from p2p.peer import BasePeerContext
from trinity.db.beacon.chain import BaseAsyncBeaconChainDB


class BeaconContext(BasePeerContext):

    def __init__(self,
                 chain_db: BaseAsyncBeaconChainDB,
                 network_id: int) -> None:
        self.chain_db = chain_db
        self.network_id = network_id
