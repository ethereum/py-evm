from p2p.peer import BasePeerContext
from trinity.db.beacon.chain import BaseAsyncBeaconChainDB
from eth2.beacon.typing import Slot
from eth2.beacon.state_machines.forks.serenity import SERENITY_CONFIG


class BeaconContext(BasePeerContext):

    def __init__(self,
                 chain_db: BaseAsyncBeaconChainDB,
                 network_id: int,
                 genesis_slot: Slot=SERENITY_CONFIG.GENESIS_SLOT) -> None:
        self.chain_db = chain_db
        self.network_id = network_id
        self.genesis_slot = genesis_slot
