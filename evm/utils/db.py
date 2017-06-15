def make_block_hash_to_number_lookup_key(block_hash):
    hash_to_number_key = b'block-hash-to-number:%s' % block_hash
    return hash_to_number_key


def make_block_number_to_hash_lookup_key(block_number):
    number_to_hash_key = b'block-number-to-hash:%d' % block_number
    return number_to_hash_key
