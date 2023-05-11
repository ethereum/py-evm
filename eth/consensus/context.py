from eth.abc import (
    AtomicDatabaseAPI,
    ConsensusContextAPI,
)


class ConsensusContext(ConsensusContextAPI):
    def __init__(self, db: AtomicDatabaseAPI):
        self.db = db
