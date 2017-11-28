def make_block_number_to_hash_lookup_key(block_number):
    number_to_hash_key = b'block-number-to-hash:%d' % block_number
    return number_to_hash_key


def make_block_hash_to_score_lookup_key(block_hash):
    return b'block-hash-to-score:%s' % block_hash
