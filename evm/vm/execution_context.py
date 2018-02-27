class ExecutionContext:
    # For shard chain, refer to the shard coinbase.
    _coinbase = None

    # For shard chian, block info of period_start_prevhash.
    _timestamp = None
    _number = None
    _difficulty = None
    _gas_limit = None
    _prev_hashes = None

    def __init__(
            self,
            coinbase,
            timestamp,
            block_number,
            difficulty,
            gas_limit,
            prev_hashes):
        self._coinbase = coinbase
        self._timestamp = timestamp
        self._block_number = block_number
        self._difficulty = difficulty
        self._gas_limit = gas_limit
        self._prev_hashes = prev_hashes

    @property
    def coinbase(self):
        return self._coinbase

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def block_number(self):
        return self._block_number

    @property
    def difficulty(self):
        return self._difficulty

    @property
    def gas_limit(self):
        return self._gas_limit

    @property
    def prev_hashes(self):
        return self._prev_hashes
