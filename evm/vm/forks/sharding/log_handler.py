import logging

from eth_utils import (
    to_dict,
)


class LogHandler(object):

    logger = logging.getLogger("evm.chain.sharding.LogHandler")

    def __init__(self, w3, history_size=256):
        self.history_size = history_size
        self.w3 = w3
        # ----------> higher score
        self.recent_block_hashes = self.get_recent_block_hashes()

    def get_recent_block_hashes(self):
        block = self.w3.eth.getBlock('latest')
        recent_hashes = [block['hash']]
        # initialize the list of recent hashes
        for _ in range(self.history_size - 1):
            # break the loop if we hit the genesis block.
            if block['number'] == 0:
                break
            block = self.w3.eth.getBlock(block['parentHash'])
            recent_hashes.append(block['hash'])
        reversed_recent_hashes = tuple(reversed(recent_hashes))
        return reversed_recent_hashes

    def check_chain_head(self):
        block = self.w3.eth.getBlock('latest')

        new_block_hashes = []

        for _ in range(self.history_size):
            if block['hash'] in self.recent_block_hashes:
                break
            new_block_hashes.append(block['hash'])
            block = self.w3.eth.getBlock(block['parentHash'])
        else:
            raise Exception('No common ancestor found for block: {0}'.format(block['hash']))

        first_common_ancestor_idx = self.recent_block_hashes.index(block['hash'])

        unchanged_hashes = self.recent_block_hashes[:first_common_ancestor_idx + 1]
        revoked_hashes = self.recent_block_hashes[first_common_ancestor_idx + 1:]

        # reverse it to comply with the order of `self.recent_block_hashes`
        reversed_new_block_hashes = tuple(reversed(new_block_hashes))
        # append new blocks to `unchanged_hashes`, and move revoked ones out of
        # `self.recent_block_hashes`
        self.recent_block_hashes = unchanged_hashes + reversed_new_block_hashes
        # keep len(self.recent_block_hashes) <= self.history_size
        self.recent_block_hashes = self.recent_block_hashes[(-1 * self.history_size):]
        return revoked_hashes, reversed_new_block_hashes

    def preprocess_block_param(self, block_param):
        if isinstance(block_param, int):
            return block_param
        elif not isinstance(block_param, str):
            raise ValueError("block parameter {0} is in wrong type".format(block_param))
        current_block_number = self.w3.eth.blockNumber
        mapping = {
            'earliest': 0,
            'latest': current_block_number,
            'pending': current_block_number + 1,
        }
        return mapping.get(block_param, block_param)

    @to_dict
    def mk_filter_params(self, from_block_number, to_block_number, address=None, topics=None):
        yield 'fromBlock', self.preprocess_block_param(from_block_number)
        yield 'toBlock', self.preprocess_block_param(to_block_number)
        if address is not None:
            yield 'address', address
        if topics is not None:
            yield 'topics', topics

    def filter_logs(self, filter_params):
        logs = self.w3.eth.getLogs(filter_params)
        return logs

    def get_new_logs(self, address=None, topics=None):
        _, new_block_hashes = self.check_chain_head()
        if len(new_block_hashes) == 0:
            return tuple()
        from_block_hash = new_block_hashes[0]
        to_block_hash = new_block_hashes[-1]
        from_block_number = self.w3.eth.getBlock(from_block_hash)['number']
        to_block_number = self.w3.eth.getBlock(to_block_hash)['number']

        filter_params = self.mk_filter_params(
            from_block_number,
            to_block_number,
            address,
            topics,
        )
        return self.filter_logs(filter_params)
