class LogHandler(object):

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
            block = self.w3.eth.getBlock(block['parentHash'])
            recent_hashes.append(block['hash'])
            # break the loop if we hit the genesis block.
            if block['number'] == 0:
                break
        reversed_recent_hashes = list(reversed(recent_hashes))
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
        reversed_new_block_hashes = list(reversed(new_block_hashes))
        # append new blocks to `unchanged_hashes`, and move revoked ones out of
        # `self.recent_block_hashes`
        self.recent_block_hashes = unchanged_hashes + reversed_new_block_hashes
        # keep len(self.recent_block_hashes) <= self.history_size
        self.recent_block_hashes = self.recent_block_hashes[(-1 * self.history_size):]
        return revoked_hashes, new_block_hashes
