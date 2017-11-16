import itertools

import rlp
from rlp.sedes import (
    big_endian_int,
    CountableList,
    binary,
)

from eth_bloom import BloomFilter

from evm.exceptions import ValidationError

from .sedes import (
    int256,
    int32,
)

from .logs import Log


class Receipt(rlp.Serializable):

    fields = [
        ('state_root', binary),
        ('gas_used', big_endian_int),
        ('bloom', int256),
        ('logs', CountableList(Log))
    ]

    def __init__(self, state_root, gas_used, logs, bloom=None):
        if bloom is None:
            bloomables = itertools.chain.from_iterable(log.bloomables for log in logs)
            bloom = int(BloomFilter.from_iterable(bloomables))

        super(Receipt, self).__init__(
            state_root=state_root,
            gas_used=gas_used,
            bloom=bloom,
            logs=logs,
        )

        for log_idx, log in enumerate(self.logs):
            if log.address not in self.bloom_filter:
                raise ValidationError(
                    "The address from the log entry at position {0} is not "
                    "present in the provided bloom filter.".format(log_idx)
                )
            for topic_idx, topic in enumerate(log.topics):
                if int32.serialize(topic) not in self.bloom_filter:
                    raise ValidationError(
                        "The topic at position {0} from the log entry at "
                        "position {1} is not present in the provided bloom "
                        "filter.".format(topic_idx, log_idx)
                    )

    @property
    def bloom_filter(self):
        return BloomFilter(self.bloom)

    @bloom_filter.setter
    def bloom_filter(self, value):
        self.bloom = int(value)
