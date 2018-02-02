import logging

from eth_utils import (
    to_dict,
)


def get_recent_block_hashes(w3, history_size):
    block = w3.eth.getBlock('latest')
    recent_hashes = [block['hash']]
    # initialize the list of recent hashes
    for _ in range(history_size - 1):
        # break the loop if we hit the genesis block.
        if block['number'] == 0:
            break
        block = w3.eth.getBlock(block['parentHash'])
        recent_hashes.append(block['hash'])
    reversed_recent_hashes = tuple(reversed(recent_hashes))
    return reversed_recent_hashes


def check_chain_head(w3, recent_block_hashes, history_size):
    block = w3.eth.getBlock('latest')

    new_block_hashes = []

    for _ in range(history_size):
        if block['hash'] in recent_block_hashes:
            break
        new_block_hashes.append(block['hash'])
        block = w3.eth.getBlock(block['parentHash'])
    else:
        raise Exception('No common ancestor found for block: {0}'.format(block['hash']))

    first_common_ancestor_idx = recent_block_hashes.index(block['hash'])

    revoked_hashes = recent_block_hashes[first_common_ancestor_idx + 1:]

    # reverse it to comply with the order of `self.recent_block_hashes`
    reversed_new_block_hashes = tuple(reversed(new_block_hashes))

    return revoked_hashes, reversed_new_block_hashes


def preprocess_block_param(w3, block_param):
    if isinstance(block_param, int):
        return block_param
    elif not isinstance(block_param, str):
        raise ValueError("block parameter {0} must be int or str type".format(block_param))
    current_block_number = w3.eth.blockNumber
    if block_param == 'earliest':
        return 0
    elif block_param == 'latest':
        return current_block_number
    elif block_param == 'pending':
        return current_block_number + 1
    else:
        raise ValueError(
            "block parameter {0} in string must be one of earliest/latest/pending".format(
                block_param,
            )
        )


class LogHandler:

    logger = logging.getLogger("evm.chain.sharding.LogHandler")

    def __init__(self, w3, history_size=256):
        self.history_size = history_size
        self.w3 = w3
        # ----------> higher score
        self.recent_block_hashes = get_recent_block_hashes(w3, history_size)

    @to_dict
    def mk_filter_params(self, from_block_number, to_block_number, address=None, topics=None):
        yield 'fromBlock', preprocess_block_param(self.w3, from_block_number)
        yield 'toBlock', preprocess_block_param(self.w3, to_block_number)
        if address is not None:
            yield 'address', address
        if topics is not None:
            yield 'topics', topics

    def get_new_logs(self, address=None, topics=None):
        # TODO: should see if we need to do something with revoked_hashes
        #       it seems reasonable to revoke logs in the blocks with hashes in `revoked_hashes`
        revoked_hashes, new_block_hashes = check_chain_head(
            self.w3,
            self.recent_block_hashes,
            self.history_size,
        )
        # determine `unchanged_block_hashes` by revoked_hashes
        # Note: use if/else to avoid self.recent_block_hashes[:-1 * 0]
        #       when len(revoked_hashes) == 0
        if len(revoked_hashes) != 0:
            unchanged_block_hashes = self.recent_block_hashes[:-1 * len(revoked_hashes)]
        else:
            unchanged_block_hashes = self.recent_block_hashes
        # append new blocks to `unchanged_hashes`, and move revoked ones out of
        # `self.recent_block_hashes`
        new_recent_block_hashes = unchanged_block_hashes + new_block_hashes
        # keep len(self.recent_block_hashes) <= self.history_size
        self.recent_block_hashes = new_recent_block_hashes[-1 * self.history_size:]

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
        return self.w3.eth.getLogs(filter_params)
